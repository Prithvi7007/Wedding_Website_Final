from datetime import date, time
from pathlib import Path

from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP
from app.services.session import establish_invitation_session


def _seed_schedule(app):
    with app.app_context():
        invitation = Invitation(
            first_name="Test",
            last_name="Guest",
            display_name="Test Guest",
            invite_token="phase3-test-token",
            is_active=True,
        )
        event = Event(
            event_id="haldi",
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
                max_guests=2,
            )
        )
        db.session.commit()
        return invitation.invitation_id


def _login(client, app, invitation_id):
    with app.app_context():
        invitation = db.session.get(Invitation, invitation_id)
        with client.session_transaction() as session:
            session["invitation_id"] = invitation.invitation_id


def test_schedule_fragment_renders_only_allowed_events(client, app):
    invitation_id = _seed_schedule(app)
    _login(client, app, invitation_id)

    response = client.get("/dashboard/tab/schedule")

    assert response.status_code == 200
    assert b"Wedding Schedule" in response.data
    assert b"Haldi" in response.data
    assert b"RSVP Now" in response.data


def test_ajax_rsvp_is_saved_and_clamped_to_permission(client, app):
    invitation_id = _seed_schedule(app)
    _login(client, app, invitation_id)

    response = client.post(
        "/dashboard/rsvp",
        data={
            "event_id": "haldi",
            "attending": "Yes",
            "guest_count": "8",
            "notes": "Vegetarian",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["guest_count"] == 2
    assert payload["summary_text"] == "Attending · 2 Guests"

    with app.app_context():
        record = db.session.scalar(
            db.select(RSVP).where(
                RSVP.invitation_id == invitation_id,
                RSVP.event_id == "haldi",
            )
        )
        assert record is not None
        assert record.attending == "Yes"
        assert record.guest_count == 2
        assert record.notes == "Vegetarian"


def test_calendar_route_is_invitation_scoped(client, app):
    invitation_id = _seed_schedule(app)
    _login(client, app, invitation_id)

    response = client.get("/dashboard/calendar/haldi.ics")

    assert response.status_code == 200
    assert response.mimetype == "text/calendar"
    assert b"BEGIN:VCALENDAR" in response.data
    assert b"SUMMARY:Haldi" in response.data


def test_schedule_assets_and_module_exist():
    assert Path("app/static/css/schedule.css").exists()
    assert Path("app/static/js/schedule.js").exists()
    for name in ("haldi", "hindu", "church"):
        assert Path(f"app/static/images/schedule/schedule-{name}-desktop.webp").exists()
        assert Path(f"app/static/images/schedule/schedule-{name}-mobile.webp").exists()


def test_schedule_dialogs_render_outside_overflow_clipped_cards(client, app):
    invitation_id = _seed_schedule(app)
    _login(client, app, invitation_id)

    response = client.get("/dashboard/tab/schedule")
    html = response.get_data(as_text=True)

    card_start = html.index('id="event-card-haldi"')
    card_end = html.index("</article>", card_start)
    modal_layer = html.index("data-schedule-modal-layer")
    rsvp_overlay = html.index('id="rsvp-overlay-haldi"')
    attire_overlay = html.index('id="attire-overlay-haldi"')

    assert card_end < modal_layer
    assert modal_layer < attire_overlay
    assert modal_layer < rsvp_overlay
