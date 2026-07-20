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
    return client.post(
        "/admin/login",
        data={"password": ADMIN_PASSWORD},
        follow_redirects=False,
    )


def _seed_dashboard(app):
    with app.app_context():
        haldi = Event(
            event_id="haldi-admin-test",
            title="Haldi",
            event_date=date(2026, 11, 19),
            start_time=time(12, 0),
            end_time=time(15, 0),
            timezone="America/New_York",
            location="Wesley Chapel",
            display_order=1,
        )
        church = Event(
            event_id="church-admin-test",
            title="Christian Wedding & Reception",
            event_date=date(2026, 11, 21),
            start_time=time(18, 0),
            end_time=time(23, 0),
            timezone="America/New_York",
            location="Tampa",
            display_order=2,
        )

        attending = Invitation(
            first_name="Attending",
            last_name="Family",
            display_name="Attending Family",
            invite_token="admin-phase1-attending",
            is_active=True,
        )
        declined = Invitation(
            first_name="Declined",
            last_name="Family",
            display_name="Declined Family",
            invite_token="admin-phase1-declined",
            is_active=True,
        )
        unanswered = Invitation(
            first_name="No",
            last_name="Response",
            display_name="No Response Household",
            invite_token="admin-phase1-unanswered",
            is_active=True,
        )
        inactive = Invitation(
            first_name="Inactive",
            last_name="Guest",
            display_name="Inactive Guest",
            invite_token="admin-phase1-inactive",
            is_active=False,
        )

        db.session.add_all(
            [
                haldi,
                church,
                attending,
                declined,
                unanswered,
                inactive,
            ]
        )
        db.session.flush()

        db.session.add_all(
            [
                InvitationEventPermission(
                    invitation_id=attending.invitation_id,
                    event_id=haldi.event_id,
                    max_guests=4,
                ),
                InvitationEventPermission(
                    invitation_id=declined.invitation_id,
                    event_id=haldi.event_id,
                    max_guests=2,
                ),
                InvitationEventPermission(
                    invitation_id=unanswered.invitation_id,
                    event_id=haldi.event_id,
                    max_guests=3,
                ),
                InvitationEventPermission(
                    invitation_id=attending.invitation_id,
                    event_id=church.event_id,
                    max_guests=4,
                ),
            ]
        )

        db.session.add_all(
            [
                RSVP(
                    invitation_id=attending.invitation_id,
                    event_id=haldi.event_id,
                    attending="Yes",
                    guest_count=3,
                    notes="Vegetarian",
                ),
                RSVP(
                    invitation_id=declined.invitation_id,
                    event_id=haldi.event_id,
                    attending="No",
                    guest_count=0,
                ),
            ]
        )
        db.session.commit()


def test_admin_dashboard_requires_authentication(client):
    response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/login")


def test_admin_login_rejects_wrong_password(client):
    response = client.post(
        "/admin/login",
        data={"password": "wrong-password"},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "was not accepted" in html


def test_admin_login_and_logout(client):
    login_response = _login(client)

    assert login_response.status_code == 302
    assert login_response.headers["Location"].endswith("/admin")

    dashboard_response = client.get("/admin")
    assert dashboard_response.status_code == 200

    logout_response = client.post(
        "/admin/logout",
        follow_redirects=False,
    )
    assert logout_response.status_code == 302
    assert logout_response.headers["Location"].endswith("/admin/login")

    protected_response = client.get("/admin", follow_redirects=False)
    assert protected_response.status_code == 302


def test_admin_dashboard_metrics_are_distinct_and_dynamic(client, app):
    _seed_dashboard(app)
    _login(client)

    response = client.get("/admin")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Active invitations" in html
    assert "No Response Household" in html
    assert "Guests attending" in html
    assert "Christian Wedding &amp; Reception" in html
    assert "Declined event responses" in html
    assert "Attending Family" in html
