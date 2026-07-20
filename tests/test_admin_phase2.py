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


def _event(
    event_id: str = "phase2-event",
    title: str = "Phase 2 Event",
) -> Event:
    return Event(
        event_id=event_id,
        title=title,
        event_date=date(2026, 11, 19),
        start_time=time(12, 0),
        end_time=time(15, 0),
        timezone="America/New_York",
        location="Tampa",
        display_order=1,
    )


def _invitation(
    token: str,
    display_name: str,
    active: bool = True,
) -> Invitation:
    return Invitation(
        first_name=display_name.split()[0],
        last_name="Household",
        display_name=display_name,
        invite_token=token,
        is_active=active,
    )


def test_invitation_routes_require_admin_login(client):
    response = client.get("/admin/invitations", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/login")


def test_invitation_list_searches_and_filters(client, app):
    with app.app_context():
        db.session.add_all(
            [
                _invitation(
                    "phase2-search-alice",
                    "Alice Family",
                ),
                _invitation(
                    "phase2-search-bob",
                    "Bob Household",
                    active=False,
                ),
            ]
        )
        db.session.commit()

    _login(client)

    response = client.get(
        "/admin/invitations?q=Alice&status=active"
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Alice Family" in html
    assert "Bob Household" not in html


def test_admin_can_create_invitation_with_event_access(client, app):
    with app.app_context():
        db.session.add(_event())
        db.session.commit()

    _login(client)

    response = client.post(
        "/admin/invitations/new",
        data={
            "first_name": "New",
            "last_name": "Guest",
            "partner_name": "Partner",
            "display_name": "New Guest Household",
            "represent_side": "Prithvi",
            "guest_group": "Friends",
            "email": "NEW@example.com",
            "phone": "813-555-0100",
            "message": "Welcome",
            "invite_message": "Private welcome",
            "is_active": "y",
            "event__phase2-event__allowed": "1",
            "event__phase2-event__max_guests": "3",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/admin/invitations/" in response.headers["Location"]

    with app.app_context():
        invitation = db.session.scalar(
            db.select(Invitation).where(
                Invitation.display_name == "New Guest Household"
            )
        )
        assert invitation is not None
        assert invitation.email == "new@example.com"
        assert invitation.invite_token
        assert len(invitation.permissions) == 1
        assert invitation.permissions[0].max_guests == 3


def test_permission_removal_is_blocked_while_rsvp_exists(client, app):
    with app.app_context():
        event = _event()
        invitation = _invitation(
            "phase2-protected-removal",
            "Protected Family",
        )
        db.session.add_all([event, invitation])
        db.session.flush()

        db.session.add(
            InvitationEventPermission(
                invitation_id=invitation.invitation_id,
                event_id=event.event_id,
                max_guests=4,
            )
        )
        db.session.add(
            RSVP(
                invitation_id=invitation.invitation_id,
                event_id=event.event_id,
                attending="Yes",
                guest_count=2,
            )
        )
        db.session.commit()
        invitation_id = invitation.invitation_id

    _login(client)

    response = client.post(
        f"/admin/invitations/{invitation_id}/edit",
        data={
            "first_name": "Protected",
            "last_name": "Family",
            "display_name": "Protected Family",
            "is_active": "y",
            "event__phase2-event__max_guests": "4",
        },
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "access cannot be removed while an RSVP exists" in html

    with app.app_context():
        permission = db.session.get(
            InvitationEventPermission,
            (invitation_id, "phase2-event"),
        )
        assert permission is not None


def test_admin_can_toggle_status_and_regenerate_token(client, app):
    with app.app_context():
        invitation = _invitation(
            "phase2-old-token",
            "Token Family",
        )
        db.session.add(invitation)
        db.session.commit()
        invitation_id = invitation.invitation_id

    _login(client)

    toggle_response = client.post(
        f"/admin/invitations/{invitation_id}/toggle-active",
        follow_redirects=False,
    )
    assert toggle_response.status_code == 302

    with app.app_context():
        invitation = db.session.get(Invitation, invitation_id)
        assert invitation is not None
        assert invitation.is_active is False
        old_token = invitation.invite_token

    regenerate_response = client.post(
        f"/admin/invitations/{invitation_id}/regenerate-token",
        data={"confirm_regenerate": "1"},
        follow_redirects=False,
    )
    assert regenerate_response.status_code == 302

    with app.app_context():
        invitation = db.session.get(Invitation, invitation_id)
        assert invitation is not None
        assert invitation.invite_token != old_token


def test_invitation_detail_contains_copyable_private_url(client, app):
    with app.app_context():
        invitation = _invitation(
            "phase2-copy-link",
            "Copy Link Family",
        )
        db.session.add(invitation)
        db.session.commit()
        invitation_id = invitation.invitation_id

    _login(client)
    response = client.get(
        f"/admin/invitations/{invitation_id}"
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "/invite/phase2-copy-link" in html
    assert "Copy Link" in html
