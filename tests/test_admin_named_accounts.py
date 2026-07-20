from app.extensions import db
from app.models import AdminAuditLog


ACCOUNT_PASSWORDS = {
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
            "password": ACCOUNT_PASSWORDS[username],
        },
        follow_redirects=False,
    )


def test_all_four_named_accounts_can_sign_in(client):
    for username in ACCOUNT_PASSWORDS:
        response = _login(client, username)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/admin")
        with client.session_transaction() as session:
            assert session["admin_username"] == username
            expected_role = (
                "admin" if username in {"prithvi", "adlin"} else "viewer"
            )
            assert session["admin_role"] == expected_role
        client.post("/admin/logout", follow_redirects=False)


def test_invalid_named_credentials_are_rejected(client):
    response = client.post(
        "/admin/login",
        data={"username": "adlin_fam", "password": "wrong"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "username or password was not accepted" in response.get_data(
        as_text=True
    )


def test_viewers_can_read_but_cannot_modify_or_export(client):
    _login(client, "adlin_fam")
    assert client.get("/admin").status_code == 200
    assert client.get("/admin/invitations").status_code == 200
    assert client.get("/admin/rsvps").status_code == 200

    new_invitation = client.get(
        "/admin/invitations/new", follow_redirects=False
    )
    assert new_invitation.status_code == 302
    assert new_invitation.headers["Location"].endswith("/admin")

    export = client.get("/admin/rsvps/export.csv", follow_redirects=False)
    assert export.status_code == 302
    assert export.headers["Location"].endswith("/admin")

    audit = client.get("/admin/audit", follow_redirects=False)
    assert audit.status_code == 302
    assert audit.headers["Location"].endswith("/admin")


def test_admins_retain_write_and_audit_access(client):
    _login(client, "prithvi")
    assert client.get("/admin/invitations/new").status_code == 200
    assert client.get("/admin/audit").status_code == 200


def test_audit_records_identify_named_actor(client, app):
    _login(client, "adlin")
    with app.app_context():
        entry = db.session.scalar(
            db.select(AdminAuditLog)
            .where(AdminAuditLog.action == "admin.login.succeeded")
            .order_by(AdminAuditLog.audit_id.desc())
        )
        assert entry is not None
        assert entry.details["actor_username"] == "adlin"
        assert entry.details["actor_display_name"] == "Adlin"
        assert entry.details["actor_role"] == "admin"


def test_viewer_navigation_hides_admin_controls(client):
    _login(client, "vk_fam")
    invitations = client.get("/admin/invitations").get_data(as_text=True)
    rsvps = client.get("/admin/rsvps").get_data(as_text=True)
    dashboard = client.get("/admin").get_data(as_text=True)
    assert "View-only access" in invitations
    assert "Add Invitation" not in invitations
    assert "Export CSV" not in rsvps
    assert ">Audit<" not in dashboard
