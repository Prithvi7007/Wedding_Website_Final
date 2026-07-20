from datetime import date, time

from app.extensions import db
from app.models import (
    AdminChangeRequest,
    Event,
    Invitation,
    InvitationEventPermission,
    RSVP,
)


PASSWORDS = {
    "prithvi": "test-admin-password-for-testing",
    "adlin": "test-adlin-password-for-testing",
    "adlin_fam": "test-adlin-family-password",
    "vk_fam": "test-vk-family-password",
}


def _login(client, username: str):
    return client.post(
        "/admin/login",
        data={
            "username": username,
            "password": PASSWORDS[username],
        },
        follow_redirects=False,
    )


def _logout(client):
    return client.post("/admin/logout", follow_redirects=False)


def _seed_request_data(app):
    with app.app_context():
        event = Event(
            event_id="request-event",
            title="Request Test Event",
            event_date=date(2026, 11, 20),
            start_time=time(9, 0),
            end_time=time(13, 0),
            timezone="America/New_York",
            location="Tampa",
            display_order=1,
        )
        invitation = Invitation(
            first_name="Original",
            last_name="Family",
            partner_name="Partner",
            display_name="Original Family",
            represent_side="Prithvi",
            guest_group="Family",
            email="original@example.com",
            phone="1112223333",
            invite_token="change-request-test-token",
            is_active=True,
        )
        db.session.add_all([event, invitation])
        db.session.flush()

        permission = InvitationEventPermission(
            invitation_id=invitation.invitation_id,
            event_id=event.event_id,
            max_guests=2,
        )
        rsvp = RSVP(
            invitation_id=invitation.invitation_id,
            event_id=event.event_id,
            attending="Maybe",
            guest_count=1,
            notes="Checking schedule",
        )
        db.session.add_all([permission, rsvp])
        db.session.commit()

        return invitation.invitation_id, event.event_id


def _submit_invitation_request(client, invitation_id: int):
    return client.post(
        f"/admin/invitations/{invitation_id}/request-change",
        data={
            "first_name": "Updated",
            "last_name": "Family",
            "partner_name": "Partner",
            "display_name": "Updated Family",
            "represent_side": "Prithvi",
            "guest_group": "Family Friends",
            "email": "updated@example.com",
            "phone": "9998887777",
            "request_note": "They confirmed their updated contact details.",
        },
        follow_redirects=False,
    )


def test_viewer_submits_household_request_without_direct_change(client, app):
    invitation_id, _event_id = _seed_request_data(app)
    _login(client, "adlin_fam")

    response = _submit_invitation_request(client, invitation_id)

    assert response.status_code == 302
    assert "/admin/requests/" in response.headers["Location"]

    with app.app_context():
        invitation = db.session.get(Invitation, invitation_id)
        change_request = db.session.scalar(
            db.select(AdminChangeRequest)
        )

        assert invitation.display_name == "Original Family"
        assert change_request is not None
        assert change_request.status == "pending"
        assert change_request.request_type == "invitation"
        assert change_request.requested_by == "adlin_fam"
        assert (
            change_request.proposed_state["display_name"]
            == "Updated Family"
        )


def test_admin_approval_applies_household_request(client, app):
    invitation_id, _event_id = _seed_request_data(app)
    _login(client, "adlin_fam")
    _submit_invitation_request(client, invitation_id)
    _logout(client)
    _login(client, "prithvi")

    with app.app_context():
        change_request_id = db.session.scalar(
            db.select(AdminChangeRequest.change_request_id)
        )

    response = client.post(
        f"/admin/requests/{change_request_id}/approve",
        data={"review_note": "Confirmed with the family."},
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        invitation = db.session.get(Invitation, invitation_id)
        change_request = db.session.get(
            AdminChangeRequest,
            change_request_id,
        )

        assert invitation.display_name == "Updated Family"
        assert invitation.email == "updated@example.com"
        assert change_request.status == "approved"
        assert change_request.reviewed_by == "prithvi"


def test_admin_approval_applies_rsvp_and_guest_limit(client, app):
    invitation_id, event_id = _seed_request_data(app)
    _login(client, "vk_fam")

    submit = client.post(
        (
            f"/admin/rsvps/invitation/{invitation_id}"
            f"/event/{event_id}/request-change"
        ),
        data={
            "attending": "Yes",
            "guest_count": "3",
            "max_guests": "3",
            "notes": "Confirmed by phone",
            "request_note": "Three family members are attending.",
        },
        follow_redirects=False,
    )
    assert submit.status_code == 302

    _logout(client)
    _login(client, "adlin")

    with app.app_context():
        change_request_id = db.session.scalar(
            db.select(AdminChangeRequest.change_request_id)
        )

    approve = client.post(
        f"/admin/requests/{change_request_id}/approve",
        data={"review_note": ""},
        follow_redirects=False,
    )
    assert approve.status_code == 302

    with app.app_context():
        permission = db.session.get(
            InvitationEventPermission,
            (invitation_id, event_id),
        )
        rsvp = db.session.scalar(
            db.select(RSVP).where(
                RSVP.invitation_id == invitation_id,
                RSVP.event_id == event_id,
            )
        )
        change_request = db.session.get(
            AdminChangeRequest,
            change_request_id,
        )

        assert permission.max_guests == 3
        assert rsvp.attending == "Yes"
        assert rsvp.guest_count == 3
        assert rsvp.notes == "Confirmed by phone"
        assert change_request.status == "approved"
        assert change_request.reviewed_by == "adlin"


def test_admin_can_reject_and_viewer_sees_reason(client, app):
    invitation_id, _event_id = _seed_request_data(app)
    _login(client, "adlin_fam")
    _submit_invitation_request(client, invitation_id)
    _logout(client)
    _login(client, "prithvi")

    with app.app_context():
        change_request_id = db.session.scalar(
            db.select(AdminChangeRequest.change_request_id)
        )

    reject = client.post(
        f"/admin/requests/{change_request_id}/reject",
        data={"review_note": "The current information is already correct."},
        follow_redirects=False,
    )
    assert reject.status_code == 302

    _logout(client)
    _login(client, "adlin_fam")
    detail = client.get(
        f"/admin/requests/{change_request_id}"
    )
    html = detail.get_data(as_text=True)

    assert detail.status_code == 200
    assert "Rejected" in html
    assert "The current information is already correct." in html


def test_viewer_can_only_see_own_requests(client, app):
    invitation_id, _event_id = _seed_request_data(app)
    _login(client, "adlin_fam")
    _submit_invitation_request(client, invitation_id)

    with app.app_context():
        change_request_id = db.session.scalar(
            db.select(AdminChangeRequest.change_request_id)
        )

    _logout(client)
    _login(client, "vk_fam")

    detail = client.get(
        f"/admin/requests/{change_request_id}",
        follow_redirects=False,
    )
    assert detail.status_code == 302
    assert detail.headers["Location"].endswith("/admin/requests/mine")

    admin_queue = client.get(
        "/admin/requests",
        follow_redirects=False,
    )
    assert admin_queue.status_code == 302
    assert admin_queue.headers["Location"].endswith("/admin")


def test_stale_request_is_not_applied(client, app):
    invitation_id, _event_id = _seed_request_data(app)
    _login(client, "adlin_fam")
    _submit_invitation_request(client, invitation_id)

    with app.app_context():
        change_request_id = db.session.scalar(
            db.select(AdminChangeRequest.change_request_id)
        )
        invitation = db.session.get(Invitation, invitation_id)
        invitation.email = "changed-after-request@example.com"
        db.session.commit()

    _logout(client)
    _login(client, "prithvi")

    response = client.post(
        f"/admin/requests/{change_request_id}/approve",
        data={"review_note": ""},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "changed after the request was submitted" in html

    with app.app_context():
        invitation = db.session.get(Invitation, invitation_id)
        change_request = db.session.get(
            AdminChangeRequest,
            change_request_id,
        )
        assert invitation.display_name == "Original Family"
        assert invitation.email == "changed-after-request@example.com"
        assert change_request.status == "pending"


def test_duplicate_pending_request_redirects_to_existing(client, app):
    invitation_id, _event_id = _seed_request_data(app)
    _login(client, "adlin_fam")

    first = _submit_invitation_request(client, invitation_id)
    second = _submit_invitation_request(client, invitation_id)

    assert first.status_code == 302
    assert second.status_code == 302
    assert second.headers["Location"] == first.headers["Location"]

    with app.app_context():
        count = db.session.scalar(
            db.select(db.func.count(AdminChangeRequest.change_request_id))
        )
        assert count == 1
