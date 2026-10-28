from datetime import date, time
from pathlib import Path

from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP


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
        token = invitation.invite_token
    response = client.post(f"/invite/{token}/open")
    assert response.status_code == 302


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


def test_weekend_calendar_is_private_and_invitation_scoped(client, app):
    invitation_id = _seed_schedule(app)
    with app.app_context():
        second = Event(
            event_id="hindu", title="Telugu, Wedding; Blessings",
            event_date=date(2026, 11, 20),
            start_time=time(9, 0), end_time=time(12, 0),
            timezone="America/New_York",
            location="Tampa, FL", description="Family, friends; celebrate",
            display_order=2,
        )
        excluded = Event(
            event_id="private", title="Private invitation only",
            event_date=date(2026, 11, 21), start_time=time(18, 0),
            end_time=time(20, 0), timezone="America/New_York",
            location="Private venue", display_order=3,
        )
        db.session.add_all([second, excluded])
        db.session.add(InvitationEventPermission(
            invitation_id=invitation_id, event_id="hindu", max_guests=2,
        ))
        db.session.commit()
    _login(client, app, invitation_id)

    response = client.get("/dashboard/calendar/weekend.ics")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert response.mimetype == "text/calendar"
    assert response.headers["Cache-Control"].startswith("private, no-store")
    assert 'filename="adlin-prithvi-weekend.ics"' in response.headers["Content-Disposition"]
    assert body.startswith("BEGIN:VCALENDAR\r\n")
    assert body.endswith("END:VCALENDAR\r\n")
    assert body.count("BEGIN:VEVENT") == 2
    assert body.count("END:VEVENT") == 2
    assert body.index("SUMMARY:Haldi") < body.index("SUMMARY:Telugu\\, Wedding\\; Blessings")
    assert "SUMMARY:Private invitation only" not in body
    assert "DTSTART;TZID=America/New_York:20261119T120000" in body
    assert "DTSTART;TZID=America/New_York:20261120T090000" in body
    assert "DESCRIPTION:Family\\, friends\\; celebrate" in body

    schedule = client.get("/dashboard/tab/schedule")
    assert b"Add my weekend to calendar" in schedule.data
    assert b"/dashboard/calendar/weekend.ics" in schedule.data


def test_weekend_calendar_requires_session_and_at_least_one_event(client, app):
    response = client.get("/dashboard/calendar/weekend.ics")
    assert response.status_code == 302

    with app.app_context():
        invitation = Invitation(
            first_name="Empty", display_name="Empty", invite_token="empty-calendar", is_active=True,
        )
        db.session.add(invitation)
        db.session.commit()
        invitation_id = invitation.invitation_id

    _login(client, app, invitation_id)
    assert client.get("/dashboard/calendar/weekend.ics").status_code == 404
    html = client.get("/dashboard/tab/schedule").get_data(as_text=True)
    assert "Add my weekend to calendar" not in html


def test_single_calendar_export_is_preserved(client, app):
    invitation_id = _seed_schedule(app)
    _login(client, app, invitation_id)
    response = client.get("/dashboard/calendar/haldi.ics")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert body.count("BEGIN:VEVENT") == 1
    assert body.count("END:VEVENT") == 1
    assert "SUMMARY:Haldi" in body
    assert "DTSTART;TZID=America/New_York:20261119T120000" in body
