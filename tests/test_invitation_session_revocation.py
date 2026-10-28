"""Guest session revocation after private invitation link rotation."""

from datetime import date, time

from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP


def _invitation_with_event(app):
    with app.app_context():
        invitation = Invitation(
            first_name="Revocation",
            display_name="Revocation Guest",
            invite_token="revocation-original-token",
            is_active=True,
        )
        event = Event(
            event_id="revocation-event",
            title="Haldi",
            event_date=date(2026, 11, 19),
            start_time=time(12, 0),
            end_time=time(15, 0),
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


def _open_guest(client, token="revocation-original-token"):
    response = client.post(f"/invite/{token}/open")
    assert response.status_code == 302


def test_guest_session_is_bound_without_disclosing_private_token(client, app):
    invitation_id = _invitation_with_event(app)
    _open_guest(client)

    with client.session_transaction() as guest_session:
        assert guest_session["invitation_id"] == invitation_id
        assert len(guest_session["invitation_token_binding"]) == 64
        assert guest_session["invitation_token_binding"] != "revocation-original-token"
    assert client.get("/dashboard?tab=welcome").status_code == 200
    assert client.get("/dashboard/tab/schedule").status_code == 200


def test_admin_token_rotation_revokes_already_open_guest_session(app):
    _invitation_with_event(app)
    guest = app.test_client()
    admin = app.test_client()

    _open_guest(guest)
    assert guest.get("/dashboard").status_code == 200

    login = admin.post(
        "/admin/login",
        data={"username": "prithvi", "password": "test-admin-password-for-testing"},
    )
    assert login.status_code == 302

    with app.app_context():
        invitation = db.session.scalar(
            db.select(Invitation).where(
                Invitation.invite_token == "revocation-original-token"
            )
        )
        invitation_id = invitation.invitation_id

    rotated = admin.post(
        f"/admin/invitations/{invitation_id}/regenerate-token",
        data={"confirm_regenerate": "1"},
    )
    assert rotated.status_code == 302

    with app.app_context():
        new_token = db.session.get(Invitation, invitation_id).invite_token
        assert new_token != "revocation-original-token"

    assert guest.get("/dashboard").status_code == 302
    with guest.session_transaction() as guest_session:
        assert "invitation_id" not in guest_session
        assert "invitation_token_binding" not in guest_session

    denied_rsvp = guest.post(
        "/dashboard/rsvp",
        data={"event_id": "revocation-event", "attending": "Yes", "guest_count": "2"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert denied_rsvp.status_code == 401
    assert guest.get(
        "/dashboard/tab/schedule",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ).status_code == 401
    assert guest.get("/dashboard/calendar/weekend.ics").status_code == 302

    with app.app_context():
        assert db.session.scalar(db.select(RSVP)) is None

    assert guest.get("/invite/revocation-original-token").status_code == 404
    assert guest.get(f"/invite/{new_token}").status_code == 200
    assert guest.post(f"/invite/{new_token}/open").status_code == 302
    assert guest.get("/dashboard").status_code == 200


def test_legacy_guest_session_without_token_binding_is_rejected(client, app):
    invitation_id = _invitation_with_event(app)
    with client.session_transaction() as guest_session:
        guest_session["invitation_id"] = invitation_id

    assert client.get("/dashboard").status_code == 302
    with client.session_transaction() as guest_session:
        assert "invitation_id" not in guest_session


def test_guest_session_is_revoked_when_invitation_deactivated(client, app):
    invitation_id = _invitation_with_event(app)
    _open_guest(client)
    with app.app_context():
        db.session.get(Invitation, invitation_id).is_active = False
        db.session.commit()

    assert client.get("/dashboard/tab/welcome").status_code == 302
    with client.session_transaction() as guest_session:
        assert "invitation_id" not in guest_session
        assert "invitation_token_binding" not in guest_session


def test_private_landing_clears_previous_token_binding(client, app):
    _invitation_with_event(app)
    _open_guest(client)
    assert client.get("/invite/revocation-original-token").status_code == 200

    with client.session_transaction() as guest_session:
        assert "invitation_id" not in guest_session
        assert "invitation_token_binding" not in guest_session
