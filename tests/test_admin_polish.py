from datetime import date, time

from app.extensions import db
from app.models import (
    Event,
    Invitation,
    InvitationEventPermission,
    RSVP,
)


ADMIN_PASSWORD = "test-admin-password-for-testing"


def _login(client):
    response = client.post(
        "/admin/login",
        data={"password": ADMIN_PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 302


def _seed_polish_data(app):
    with app.app_context():
        event = Event(
            event_id="polish-event",
            title="Polish Test Event",
            event_date=date(2026, 11, 20),
            start_time=time(9, 0),
            end_time=time(13, 0),
            timezone="America/New_York",
            location="Tampa",
            display_order=1,
        )
        responding = Invitation(
            first_name="Responding",
            last_name="Family",
            display_name="Responding Family",
            invite_token="polish-responding",
            represent_side="Prithvi",
            guest_group="Family",
            is_active=True,
        )
        unanswered = Invitation(
            first_name="Unanswered",
            last_name="Family",
            display_name="Unanswered Family",
            invite_token="polish-unanswered",
            represent_side="Adlin",
            guest_group="Friends",
            is_active=True,
        )

        db.session.add_all([event, responding, unanswered])
        db.session.flush()
        db.session.add_all(
            [
                InvitationEventPermission(
                    invitation_id=responding.invitation_id,
                    event_id=event.event_id,
                    max_guests=3,
                ),
                InvitationEventPermission(
                    invitation_id=unanswered.invitation_id,
                    event_id=event.event_id,
                    max_guests=2,
                ),
            ]
        )
        db.session.add(
            RSVP(
                invitation_id=responding.invitation_id,
                event_id=event.event_id,
                attending="Yes",
                guest_count=2,
                notes="Window seat requested",
            )
        )
        db.session.commit()


def test_admin_dashboard_is_actionable_and_uses_clean_labels(client, app):
    _seed_polish_data(app)
    _login(client)

    response = client.get("/admin")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "admin-metric-link" in html
    assert "Households responding" in html
    assert "No RSVP submitted" in html
    assert "Declined event responses" in html
    assert "Maximum invited" in html
    assert "Confirmed attendance" in html
    assert "data-row-href" in html
    assert "Unanswered Family" in html
    assert "/admin/invitations/" in html


def test_admin_directories_have_fast_filter_controls(client, app):
    _seed_polish_data(app)
    _login(client)

    invitation_response = client.get(
        "/admin/invitations?status=active&represent=Prithvi"
    )
    invitation_html = invitation_response.get_data(as_text=True)

    assert invitation_response.status_code == 200
    assert "data-auto-submit" in invitation_html
    assert 'aria-label="Active invitation filters"' in invitation_html
    assert "Represent:" in invitation_html
    assert "Prithvi" in invitation_html
    assert "Clear all" in invitation_html

    rsvp_response = client.get(
        "/admin/rsvps?response=no_response&event=polish-event"
    )
    rsvp_html = rsvp_response.get_data(as_text=True)

    assert rsvp_response.status_code == 200
    assert "Invitation-event records" in rsvp_html
    assert 'aria-label="Active RSVP filters"' in rsvp_html
    assert "Response:" in rsvp_html
    assert "No response" in rsvp_html
    assert "Polish Test Event" in rsvp_html


def test_admin_audit_filters_use_the_same_polished_interaction(client, app):
    _login(client)

    response = client.get("/admin/audit?action=admin.login.succeeded")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "data-auto-submit" in html
    assert 'aria-label="Active audit filters"' in html
    assert "Clear all" in html
