from datetime import date, time
import json

from app.extensions import db
from app.models import (
    AdminAuditLog,
    AdminLoginAttempt,
    Event,
    Invitation,
    InvitationEventPermission,
    RSVP,
)


ADMIN_PASSWORD = "test-admin-password-for-testing"


def _login(client, password=ADMIN_PASSWORD):
    return client.post(
        "/admin/login",
        data={"password": password},
        follow_redirects=False,
    )


def _event():
    return Event(
        event_id="phase4-event",
        title="Phase 4 Event",
        event_date=date(2026, 11, 21),
        start_time=time(17, 0),
        end_time=time(22, 0),
        timezone="America/New_York",
        location="Tampa",
        display_order=1,
    )


def _invitation():
    return Invitation(
        first_name="Audit",
        last_name="Family",
        display_name="Audit Family",
        invite_token="phase4-private-token",
        is_active=True,
    )


def test_admin_responses_are_not_cached(client):
    response = client.get("/admin/login")

    assert response.status_code == 200
    assert "no-store" in response.headers["Cache-Control"]
    assert response.headers["X-Robots-Tag"] == (
        "noindex, nofollow, noarchive"
    )


def test_login_rate_limit_blocks_repeated_failures(client, app):
    app.config.update(
        ADMIN_LOGIN_MAX_FAILURES=3,
        ADMIN_LOGIN_FAILURE_WINDOW_SECONDS=900,
        ADMIN_LOGIN_LOCKOUT_SECONDS=1800,
    )

    for _ in range(3):
        response = _login(client, "wrong-password")
        assert response.status_code == 200

    blocked = _login(client, ADMIN_PASSWORD)

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0

    with app.app_context():
        attempts = list(
            db.session.scalars(
                db.select(AdminLoginAttempt).where(
                    AdminLoginAttempt.succeeded.is_(False)
                )
            ).all()
        )
        assert len(attempts) == 3

        blocked_audit = db.session.scalar(
            db.select(AdminAuditLog).where(
                AdminAuditLog.action == "admin.login.blocked"
            )
        )
        assert blocked_audit is not None


def test_successful_login_clears_failed_attempts(client, app):
    assert _login(client, "wrong-one").status_code == 200
    assert _login(client, "wrong-two").status_code == 200

    success = _login(client)

    assert success.status_code == 302

    with app.app_context():
        failed_count = db.session.scalar(
            db.select(db.func.count(AdminLoginAttempt.attempt_id)).where(
                AdminLoginAttempt.succeeded.is_(False)
            )
        )
        succeeded_count = db.session.scalar(
            db.select(db.func.count(AdminLoginAttempt.attempt_id)).where(
                AdminLoginAttempt.succeeded.is_(True)
            )
        )
        assert failed_count == 0
        assert succeeded_count == 1

        audit = db.session.scalar(
            db.select(AdminAuditLog).where(
                AdminAuditLog.action == "admin.login.succeeded"
            )
        )
        assert audit is not None
        assert audit.session_id


def test_invitation_creation_is_audited_without_raw_token(client, app):
    with app.app_context():
        db.session.add(_event())
        db.session.commit()

    assert _login(client).status_code == 302

    response = client.post(
        "/admin/invitations/new",
        data={
            "first_name": "Audit",
            "last_name": "Family",
            "display_name": "Audited Household",
            "is_active": "y",
            "event__phase4-event__allowed": "1",
            "event__phase4-event__max_guests": "3",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        invitation = db.session.scalar(
            db.select(Invitation).where(
                Invitation.display_name == "Audited Household"
            )
        )
        audit = db.session.scalar(
            db.select(AdminAuditLog).where(
                AdminAuditLog.action == "invitation.created"
            )
        )

        assert invitation is not None
        assert audit is not None
        serialized = json.dumps(audit.after_state)
        assert invitation.invite_token not in serialized
        assert audit.after_state["token_fingerprint"]
        assert audit.after_state["permissions"] == [
            {
                "event_id": "phase4-event",
                "max_guests": 3,
            }
        ]


def test_rsvp_update_and_clear_are_audited(client, app):
    with app.app_context():
        event = _event()
        invitation = _invitation()
        db.session.add_all([event, invitation])
        db.session.flush()
        permission = InvitationEventPermission(
            invitation_id=invitation.invitation_id,
            event_id=event.event_id,
            max_guests=4,
        )
        db.session.add(permission)
        db.session.commit()
        invitation_id = invitation.invitation_id

    assert _login(client).status_code == 302

    create_response = client.post(
        (
            f"/admin/rsvps/invitation/{invitation_id}"
            "/event/phase4-event/edit"
        ),
        data={
            "attending": "Yes",
            "guest_count": "2",
            "notes": "Audit note",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 302

    with app.app_context():
        rsvp = db.session.scalar(db.select(RSVP))
        assert rsvp is not None
        rsvp_id = rsvp.rsvp_id

        created_audit = db.session.scalar(
            db.select(AdminAuditLog).where(
                AdminAuditLog.action == "rsvp.created"
            )
        )
        assert created_audit is not None
        assert created_audit.after_state["guest_count"] == 2

    clear_response = client.post(
        f"/admin/rsvps/{rsvp_id}/clear",
        data={"confirm_clear": "1"},
        follow_redirects=False,
    )
    assert clear_response.status_code == 302

    with app.app_context():
        assert db.session.get(RSVP, rsvp_id) is None
        cleared_audit = db.session.scalar(
            db.select(AdminAuditLog).where(
                AdminAuditLog.action == "rsvp.cleared"
            )
        )
        assert cleared_audit is not None
        assert cleared_audit.before_state["rsvp_id"] == rsvp_id


def test_audit_history_is_protected_and_visible(client, app):
    protected = client.get("/admin/audit", follow_redirects=False)
    assert protected.status_code == 302
    assert protected.headers["Location"].endswith("/admin/login")

    assert _login(client).status_code == 302
    response = client.get("/admin/audit")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Audit History" in html
    assert "admin · login · succeeded" in html
