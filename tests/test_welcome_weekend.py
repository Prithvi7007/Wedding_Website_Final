"""Invitation-scoped Welcome story and RSVP presentation."""
from datetime import date, time

from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP


def _make_event(event_id: str, title: str, order: int) -> Event:
    return Event(
        event_id=event_id,
        title=title,
        event_date=date(2026, 11, 18 + order),
        start_time=time(12, 0),
        end_time=time(15, 0),
        timezone="America/New_York",
        location="Wesley Chapel, FL",
        venue_name="Celebration Hall",
        display_order=order,
    )


def _login(client, invitation_id):
    with client.session_transaction() as session:
        session["invitation_id"] = invitation_id


def test_welcome_shows_only_invited_events_and_real_rsvp_states(client, app):
    with app.app_context():
        guest = Invitation(
            first_name="Weekend", display_name="Weekend Guest", invite_token="weekend-guest", is_active=True
        )
        other = Invitation(
            first_name="Other", display_name="Other Guest", invite_token="other-guest", is_active=True
        )
        events = [
            _make_event("haldi", "Golden Haldi", 1),
            _make_event("hindu", "Telugu Ceremony", 2),
            _make_event("church", "Wedding Reception", 3),
            _make_event("dinner", "Family Dinner", 4),
            _make_event("private", "PRIVATE EXCLUDED CELEBRATION", 5),
        ]
        db.session.add_all([guest, other, *events])
        db.session.flush()
        for event in events[:4]:
            db.session.add(InvitationEventPermission(
                invitation_id=guest.invitation_id,
                event_id=event.event_id,
                max_guests=2,
            ))
        db.session.add(InvitationEventPermission(
            invitation_id=other.invitation_id,
            event_id="private",
            max_guests=4,
        ))
        for event_id, attending, count in [
            ("haldi", "Yes", 2),
            ("hindu", "Maybe", 0),
            ("church", "No", 0),
        ]:
            db.session.add(RSVP(
                invitation_id=guest.invitation_id,
                event_id=event_id,
                attending=attending,
                guest_count=count,
            ))
        db.session.add(RSVP(
            invitation_id=other.invitation_id,
            event_id="private", attending="Yes", guest_count=4,
        ))
        db.session.commit()
        guest_id = guest.invitation_id

    _login(client, guest_id)
    for url in ("/dashboard?tab=welcome", "/dashboard/tab/welcome"):
        response = client.get(url)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'data-weekend-event-id="haldi"' in html
        assert html.count("data-weekend-event-id=") == 4
        assert "PRIVATE EXCLUDED CELEBRATION" not in html
        assert "Attending · 2 guests" in html
        assert "Maybe · Response noted" in html
        assert "Unable to attend" in html
        assert "Awaiting your RSVP" in html
        assert "Your reply is saved for 3" in html
        assert "of 4 celebrations." in html
        assert "Continue your RSVP" in html
        assert html.index("Golden Haldi") < html.index("Telugu Ceremony")
        assert html.index("Telugu Ceremony") < html.index("Wedding Reception")
        assert html.index("Wedding Reception") < html.index("Family Dinner")


def test_welcome_keeps_original_hero_without_invited_events(client, app):
    with app.app_context():
        guest = Invitation(
            first_name="No events", display_name="No events", invite_token="none-welcome", is_active=True
        )
        db.session.add(guest)
        db.session.commit()
        invitation_id = guest.invitation_id

    _login(client, invitation_id)
    response = client.get("/dashboard/tab/welcome")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "View Your Schedule" in html
    assert 'class="welcome-weekend"' not in html
    assert "A weekend written for you" not in html
