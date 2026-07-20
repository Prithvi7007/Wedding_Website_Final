from datetime import date, time

from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP


ADMIN_PASSWORD = "test-admin-password-for-testing"


def _login(client):
    response = client.post(
        "/admin/login",
        data={"password": ADMIN_PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 302


def _event(event_id="phase3-event", title="Phase 3 Event"):
    return Event(
        event_id=event_id,
        title=title,
        event_date=date(2026, 11, 21),
        start_time=time(17, 0),
        end_time=time(22, 0),
        timezone="America/New_York",
        location="Tampa",
        display_order=1,
    )


def _invitation(token, display_name):
    return Invitation(
        first_name="Phase",
        last_name="Three",
        display_name=display_name,
        invite_token=token,
        is_active=True,
    )


def _permission(invitation_id, event_id, max_guests=4):
    return InvitationEventPermission(
        invitation_id=invitation_id,
        event_id=event_id,
        max_guests=max_guests,
    )


def test_rsvp_routes_require_admin_login(client):
    response = client.get("/admin/rsvps", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/login")


def test_rsvp_directory_distinguishes_no_response_from_declined(client, app):
    with app.app_context():
        event = _event()
        no_response = _invitation("phase3-no-response-token", "No Response Family")
        declined = _invitation("phase3-declined-token", "Declined Family")
        db.session.add_all([event, no_response, declined])
        db.session.flush()
        db.session.add_all([
            _permission(no_response.invitation_id, event.event_id),
            _permission(declined.invitation_id, event.event_id),
            RSVP(
                invitation_id=declined.invitation_id,
                event_id=event.event_id,
                attending="No",
                guest_count=0,
            ),
        ])
        db.session.commit()

    _login(client)
    no_response_page = client.get("/admin/rsvps?response=no_response").get_data(as_text=True)
    declined_page = client.get("/admin/rsvps?response=no").get_data(as_text=True)

    assert "No Response Family" in no_response_page
    assert "Declined Family" not in no_response_page
    assert "Declined Family" in declined_page
    assert "No Response Family" not in declined_page


def test_admin_can_create_rsvp_and_guest_limit_is_enforced(client, app):
    with app.app_context():
        event = _event()
        invitation = _invitation("phase3-create-token", "Create RSVP Family")
        db.session.add_all([event, invitation])
        db.session.flush()
        db.session.add(_permission(invitation.invitation_id, event.event_id, 2))
        db.session.commit()
        invitation_id = invitation.invitation_id

    _login(client)
    path = f"/admin/rsvps/invitation/{invitation_id}/event/phase3-event/edit"

    too_many = client.post(
        path,
        data={"attending": "Yes", "guest_count": "3", "notes": ""},
        follow_redirects=True,
    )
    html = too_many.get_data(as_text=True)
    assert "cannot exceed this invitation" in html

    with app.app_context():
        assert db.session.scalar(db.select(RSVP)) is None

    valid = client.post(
        path,
        data={"attending": "Yes", "guest_count": "2", "notes": "Vegetarian meal"},
        follow_redirects=False,
    )
    assert valid.status_code == 302

    with app.app_context():
        rsvp = db.session.scalar(db.select(RSVP))
        assert rsvp is not None
        assert rsvp.attending == "Yes"
        assert rsvp.guest_count == 2
        assert rsvp.notes == "Vegetarian meal"


def test_declined_rsvp_always_stores_zero_guests(client, app):
    with app.app_context():
        event = _event()
        invitation = _invitation("phase3-decline-zero-token", "Zero Guests Family")
        db.session.add_all([event, invitation])
        db.session.flush()
        db.session.add(_permission(invitation.invitation_id, event.event_id, 5))
        db.session.commit()
        invitation_id = invitation.invitation_id

    _login(client)
    response = client.post(
        f"/admin/rsvps/invitation/{invitation_id}/event/phase3-event/edit",
        data={"attending": "No", "guest_count": "4", "notes": "Unable to attend"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        rsvp = db.session.scalar(db.select(RSVP))
        assert rsvp is not None
        assert rsvp.attending == "No"
        assert rsvp.guest_count == 0


def test_admin_can_clear_rsvp_without_removing_permission(client, app):
    with app.app_context():
        event = _event()
        invitation = _invitation("phase3-clear-token", "Clear RSVP Family")
        db.session.add_all([event, invitation])
        db.session.flush()
        permission = _permission(invitation.invitation_id, event.event_id, 3)
        rsvp = RSVP(
            invitation_id=invitation.invitation_id,
            event_id=event.event_id,
            attending="Maybe",
            guest_count=1,
        )
        db.session.add_all([permission, rsvp])
        db.session.commit()
        rsvp_id = rsvp.rsvp_id
        invitation_id = invitation.invitation_id

    _login(client)
    response = client.post(
        f"/admin/rsvps/{rsvp_id}/clear",
        data={"confirm_clear": "1"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        assert db.session.get(RSVP, rsvp_id) is None
        assert db.session.get(
            InvitationEventPermission,
            (invitation_id, "phase3-event"),
        ) is not None


def test_filtered_csv_export_includes_no_response_and_is_formula_safe(client, app):
    with app.app_context():
        event = _event()
        invitation = _invitation("phase3-csv-token", "=Formula Family")
        db.session.add_all([event, invitation])
        db.session.flush()
        db.session.add(_permission(invitation.invitation_id, event.event_id))
        db.session.commit()

    _login(client)
    response = client.get("/admin/rsvps/export.csv?response=no_response")
    csv_text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "No response" in csv_text
    assert "'=Formula Family" in csv_text
