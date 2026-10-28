"""Read-only Guest Experience V2 preview security and personalization tests."""

from datetime import date, time

from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP


def _seed_preview(app):
    with app.app_context():
        guest = Invitation(
            first_name="Preview",
            display_name="The Example Family",
            invite_token="guest-v2-private-token",
            invite_message="We would love to celebrate with you.",
            is_active=True,
        )
        allowed = Event(
            event_id="haldi",
            title="Haldi",
            event_date=date(2026, 11, 19),
            start_time=time(11, 0),
            end_time=time(14, 0),
            timezone="America/New_York",
            venue_name="Private Residence",
            location="Wesley Chapel, FL",
            display_order=1,
        )
        blocked = Event(
            event_id="uninvited",
            title="Private Uninvited Celebration",
            event_date=date(2026, 11, 20),
            start_time=time(15, 0),
            end_time=time(17, 0),
            timezone="America/New_York",
            location="Private location",
            display_order=2,
        )
        db.session.add_all([guest, allowed, blocked])
        db.session.flush()
        db.session.add(
            InvitationEventPermission(
                invitation_id=guest.invitation_id,
                event_id=allowed.event_id,
                max_guests=2,
            )
        )
        db.session.commit()
        return guest.invitation_id


def test_v2_preview_requires_private_invitation_session(client):
    response = client.get("/dashboard/preview/guest-v2")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_v2_preview_uses_existing_guest_permissions_and_read_only_rsvp(client, app):
    invitation_id = _seed_preview(app)
    assert client.post("/invite/guest-v2-private-token/open").status_code == 302

    response = client.get("/dashboard/preview/guest-v2")
    assert response.status_code == 200
    assert response.headers["Cache-Control"].startswith("private, no-store")
    assert "noindex" in response.headers["X-Robots-Tag"]

    html = response.get_data(as_text=True)
    assert "The Example Family" in html
    assert "We would love to celebrate with you." in html
    assert "Haldi" in html
    assert "11:00 AM" in html
    assert "Private Residence" in html
    assert "Awaiting your RSVP" in html
    assert "Private Uninvited Celebration" not in html
    assert "Private location" not in html
    assert 'href="/dashboard?tab=schedule&amp;event=haldi"' in html
    assert 'name="attending"' not in html
    assert '<form' not in html
    assert "guest-v2.css" in html
    assert "v2-hero-atmosphere" in html
    assert "guest-v2-glass.css" in html

    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(RSVP.rsvp_id))) == 0

        # The display must reflect an existing saved RSVP without editing it.
        db.session.add(
            RSVP(
                invitation_id=invitation_id,
                event_id="haldi",
                attending="Yes",
                guest_count=2,
                notes="A dietary note",
            )
        )
        db.session.commit()

    updated = client.get("/dashboard/preview/guest-v2")
    assert b"You're attending" in updated.data
    assert b"2 guests" in updated.data
    assert b"A dietary note" not in updated.data


def test_v2_preview_does_not_replace_live_navigation(client, app):
    _seed_preview(app)
    client.post("/invite/guest-v2-private-token/open")
    current = client.get("/dashboard?tab=welcome")
    current_html = current.get_data(as_text=True)

    assert current.status_code == 200
    assert 'class="dashboard-shell"' in current_html
    assert "Guest concept" not in current_html
    assert 'guest-v2.css' not in current_html
    assert 'guest-v2-glass.css' not in current_html
    assert "/dashboard/preview/guest-v2" not in current_html
