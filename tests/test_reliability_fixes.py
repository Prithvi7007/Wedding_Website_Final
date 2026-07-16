from __future__ import annotations

from datetime import date, time
from pathlib import Path

from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP


def _seed_invitation_and_event(app):
    with app.app_context():
        invitation = Invitation(
            first_name="Reliability",
            last_name="Guest",
            display_name="Reliability Guest",
            invite_token="reliability-fixes-token",
            is_active=True,
        )
        event = Event(
            event_id="reliability-haldi",
            title="Haldi",
            event_date=date(2026, 11, 19),
            start_time=time(12, 0),
            end_time=time(15, 0),
            timezone="America/New_York",
            short_date="Nov 19",
            venue_name="Wesley Chapel",
            location="Wesley Chapel, FL",
            description="A joyful celebration",
            attire_heading="Haldi Festive",
            attire="Yellow and festive attire",
            display_order=1,
        )
        db.session.add_all([invitation, event])
        db.session.flush()
        db.session.add(
            InvitationEventPermission(
                invitation_id=invitation.invitation_id,
                event_id=event.event_id,
                max_guests=3,
            )
        )
        db.session.commit()
        return invitation.invitation_id, event.event_id


def _login(client, invitation_id):
    with client.session_transaction() as session:
        session["invitation_id"] = invitation_id


def test_expired_ajax_fragment_returns_401(client):
    response = client.get(
        "/dashboard/tab/schedule",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == 401
    payload = response.get_json()
    assert payload["success"] is False
    assert "session expired" in payload["message"].lower()


def test_fragment_client_returns_home_on_401():
    source = Path("app/static/js/tabs.js").read_text(encoding="utf-8")

    assert "response.status === 401" in source
    assert 'window.location.assign("/")' in source


def test_yes_rsvp_rejects_zero_guests(client, app):
    invitation_id, event_id = _seed_invitation_and_event(app)
    _login(client, invitation_id)

    response = client.post(
        "/dashboard/rsvp",
        data={
            "event_id": event_id,
            "attending": "Yes",
            "guest_count": "0",
            "notes": "",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == 400
    assert "at least one" in response.get_json()["message"].lower()

    with app.app_context():
        saved = db.session.scalar(
            db.select(RSVP).where(
                RSVP.invitation_id == invitation_id,
                RSVP.event_id == event_id,
            )
        )
        assert saved is None


def test_ios_petals_use_one_canvas_layer():
    shell = Path("app/templates/dashboard/shell.html").read_text(
        encoding="utf-8"
    )
    script = Path("app/static/js/schedule.js").read_text(
        encoding="utf-8"
    )
    css = Path("app/static/css/schedule.css").read_text(
        encoding="utf-8"
    )

    assert 'id="rsvp-petal-canvas"' in shell
    assert "function burstCanvasPetals(eventId)" in script
    assert "requestAnimationFrame(frame)" in script
    assert "isIos() && burstCanvasPetals(eventId)" in script
    assert ".rsvp-petal-canvas" in css


def test_private_invitation_notice_pages_are_styled(client):
    home = client.get("/")
    assert home.status_code == 200
    home_html = home.get_data(as_text=True)
    assert "Private Wedding Website" in home_html
    assert "Please contact Adlin or Prithvi" in home_html
    assert "invitation-notice" in home_html

    invalid = client.get("/invite/not-a-real-token")
    assert invalid.status_code == 404
    invalid_html = invalid.get_data(as_text=True)
    assert "We could not open this invitation" in invalid_html
    assert "Please contact Adlin or Prithvi" in invalid_html
    assert "invitation-notice" in invalid_html


def test_telugu_wedding_kicker_mentions_lunch():
    source = Path("app/dashboard/presenters.py").read_text(
        encoding="utf-8"
    )

    assert "Traditional Telugu ceremony, Lunch and blessings" in source
