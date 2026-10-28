"""Failure-path tests for RSVP email delivery. No external email requests."""

from datetime import date, time

import resend

from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP
from app.services import notifications_legacy as delivery


class FakeProviderError(Exception):
    def __init__(self, code, error_type):
        super().__init__("private guest notes must never reach logs")
        self.code = code
        self.error_type = error_type


def _notification():
    return delivery.RSVPNotification(
        guest_name="Private Guest",
        event_title="Haldi",
        current=delivery.RSVPState("Yes", 2, "Sensitive dietary request"),
    )


def test_transient_email_failure_retries_with_one_idempotency_key(monkeypatch):
    requests = []
    sleeps = []

    def fake_send(payload, options):
        requests.append((dict(payload), dict(options)))
        if len(requests) == 1:
            raise FakeProviderError(503, "api_error")
        return {"id": "mock-accepted-id"}

    monkeypatch.setattr(resend.Emails, "send", fake_send)
    monkeypatch.setattr(delivery.time, "sleep", sleeps.append)

    result = delivery.send_rsvp_notification(
        _notification(), api_key="fake-key", recipients=["host@example.test"]
    )

    assert result.sent is True
    assert result.message_id == "mock-accepted-id"
    assert len(requests) == 2
    assert requests[0] == requests[1]
    assert requests[0][1]["idempotency_key"].startswith("wedding-rsvp/")
    assert sleeps == [0.15]


def test_permanent_email_failure_is_not_retried_or_logged_with_pii(monkeypatch, caplog):
    attempts = []

    def fake_send(payload, options):
        attempts.append(options)
        raise FakeProviderError(403, "authorization_error")

    monkeypatch.setattr(resend.Emails, "send", fake_send)
    result = delivery.send_rsvp_notification(
        _notification(), api_key="fake-key", recipients=["host@example.test"]
    )

    assert result.sent is False
    assert result.error == "permanent_delivery_failure"
    assert len(attempts) == 1
    assert "Private Guest" not in caplog.text
    assert "Sensitive dietary request" not in caplog.text
    assert "private guest notes must never reach logs" not in caplog.text


def test_retryable_transport_error_is_bounded(monkeypatch):
    attempts = []

    def fake_send(payload, options):
        attempts.append(options)
        raise FakeProviderError(500, "HttpClientError")

    monkeypatch.setattr(resend.Emails, "send", fake_send)
    monkeypatch.setattr(delivery.time, "sleep", lambda delay: None)

    result = delivery.send_rsvp_notification(
        _notification(), api_key="fake-key", recipients=["host@example.test"]
    )
    assert result.sent is False
    assert result.error == "temporary_delivery_failure"
    assert len(attempts) == 2
    assert attempts[0] == attempts[1]


def test_provider_response_without_id_does_not_claim_sent(monkeypatch):
    requests = []
    monkeypatch.setattr(
        resend.Emails,
        "send",
        lambda payload, options: requests.append(options) or {},
    )
    result = delivery.send_rsvp_notification(
        _notification(), api_key="fake-key", recipients=["host@example.test"]
    )
    assert result.sent is False
    assert result.error == "unconfirmed_response"
    assert len(requests) == 1


def test_missing_provider_configuration_does_not_attempt_to_send(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setattr(
        resend.Emails,
        "send",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Must not send")),
    )
    result = delivery.send_rsvp_notification(_notification())
    assert result.sent is False
    assert result.error == "RESEND_API_KEY is not configured"


def test_rsvp_is_saved_even_if_notification_helper_unexpectedly_crashes(
    client, app, monkeypatch,
):
    with app.app_context():
        invitation = Invitation(
            first_name="Email",
            display_name="Email Test Guest",
            invite_token="email-test-guest",
            is_active=True,
        )
        event = Event(
            event_id="email-test-event",
            title="Haldi",
            event_date=date(2026, 11, 19),
            start_time=time(12, 0),
            end_time=time(14, 0),
            timezone="America/New_York",
            location="Tampa",
        )
        db.session.add_all([invitation, event])
        db.session.flush()
        db.session.add(
            InvitationEventPermission(
                invitation_id=invitation.invitation_id,
                event_id=event.event_id,
                max_guests=2,
            )
        )
        db.session.commit()
        invitation_id = invitation.invitation_id

    assert client.post("/invite/email-test-guest/open").status_code == 302

    def crash(_notification):
        raise RuntimeError("Simulated post-commit notification crash")

    monkeypatch.setattr("app.dashboard.routes.send_rsvp_notification", crash)
    result = client.post(
        "/dashboard/rsvp",
        data={
            "event_id": "email-test-event",
            "attending": "Yes",
            "guest_count": "2",
            "notes": "Vegetarian",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert result.status_code == 200
    assert result.get_json()["success"] is True
    with app.app_context():
        saved = db.session.scalar(
            db.select(RSVP).where(RSVP.invitation_id == invitation_id)
        )
        assert saved is not None
        assert saved.attending == "Yes"
        assert saved.guest_count == 2


def test_sync_resend_http_timeout_is_shorter_than_original_default():
    assert delivery.EMAIL_REQUEST_TIMEOUT_SECONDS == 5
    assert resend.default_http_client._timeout == 5
