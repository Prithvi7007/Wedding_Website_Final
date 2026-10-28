"""Atomic guest RSVP regression checks (disposable database only)."""

from datetime import date, time

from sqlalchemy import event as sa_event
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP
from app.repositories.events import EventRepository
from app.services.notifications_legacy import NotificationResult


def _seed_guest(app):
    with app.app_context():
        invitation = Invitation(
            first_name="Atomic",
            display_name="Atomic Guest",
            invite_token="atomic-rsvp-guest",
            is_active=True,
        )
        event = Event(
            event_id="atomic-event",
            title="Haldi",
            event_date=date(2026, 11, 19),
            start_time=time(12, 0),
            end_time=time(14, 0),
            timezone="America/New_York",
            location="Tampa, FL",
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
        return invitation.invitation_id


def _post_rsvp(client, attending, count, notes):
    return client.post(
        "/dashboard/rsvp",
        data={
            "event_id": "atomic-event",
            "attending": attending,
            "guest_count": str(count),
            "notes": notes,
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )


def test_repeated_guest_saves_update_one_rsvp_and_preserve_previous_state(
    client, app, monkeypatch,
):
    invitation_id = _seed_guest(app)
    assert client.post("/invite/atomic-rsvp-guest/open").status_code == 302

    sent = []

    def record_notification(notification):
        sent.append(notification)
        return NotificationResult(sent=True, message_id="test-only")

    monkeypatch.setattr(
        "app.dashboard.routes.send_rsvp_notification",
        record_notification,
    )

    first = _post_rsvp(client, "Yes", 2, "Vegetarian")
    assert first.status_code == 200
    assert first.get_json()["guest_count"] == 2

    with app.app_context():
        first_id = db.session.scalar(db.select(RSVP.rsvp_id))

    second = _post_rsvp(client, "Maybe", 1, "Will confirm")
    assert second.status_code == 200
    assert second.get_json()["summary_text"] == "Maybe · Response Pending"

    third = _post_rsvp(client, "No", 2, "Cannot attend")
    assert third.status_code == 200
    assert third.get_json()["guest_count"] == 0

    with app.app_context():
        records = db.session.scalars(
            db.select(RSVP).where(RSVP.invitation_id == invitation_id)
        ).all()
        assert len(records) == 1
        assert records[0].rsvp_id == first_id
        assert records[0].attending == "No"
        assert records[0].guest_count == 0
        assert records[0].notes == "Cannot attend"

    assert len(sent) == 3
    assert sent[0].previous is None
    assert sent[1].previous.attending == "Yes"
    assert sent[1].previous.guest_count == 2
    assert sent[2].previous.attending == "Maybe"
    assert sent[2].previous.notes == "Will confirm"


def test_guest_rsvp_lookup_locks_only_its_invitation_event_permission(app):
    invitation_id = _seed_guest(app)
    collected = []

    def capture_statement(execute_state):
        statement = execute_state.statement
        if getattr(statement, "_for_update_arg", None) is not None:
            collected.append(str(statement.compile(dialect=postgresql.dialect())))

    sa_event.listen(Session, "do_orm_execute", capture_statement)
    try:
        with app.app_context():
            allowed = EventRepository.allowed_event_for_invitation(
                invitation_id,
                "atomic-event",
                for_update=True,
            )
            assert allowed is not None
            assert allowed.max_guests == 2
    finally:
        sa_event.remove(Session, "do_orm_execute", capture_statement)

    assert len(collected) == 1
    assert "FOR UPDATE OF invitation_event_permissions" in collected[0]
    assert "JOIN invitation_event_permissions" in collected[0]
