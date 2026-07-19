from __future__ import annotations

from app.extensions import db
from app.models import Invitation


def _seed_private_invitation(app):
    with app.app_context():
        invitation = Invitation(
            first_name="Landing",
            last_name="Guest",
            display_name="Landing Guest",
            invite_token="landing-page-test-token",
            is_active=True,
        )
        db.session.add(invitation)
        db.session.commit()
        return invitation.invitation_id


def test_private_link_stops_on_invitation_landing(client, app):
    _seed_private_invitation(app)

    response = client.get("/invite/landing-page-test-token")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Welcome, Landing Guest" in html
    assert "Open Invitation" in html
    assert "Your private invitation and RSVP await." in html

    with client.session_transaction() as session:
        assert session.get("invitation_id") is None


def test_private_link_clears_an_existing_invitation_session(client, app):
    invitation_id = _seed_private_invitation(app)

    with client.session_transaction() as session:
        session["invitation_id"] = invitation_id

    response = client.get("/invite/landing-page-test-token")

    assert response.status_code == 200
    with client.session_transaction() as session:
        assert session.get("invitation_id") is None


def test_open_invitation_button_enters_dashboard_welcome(client, app):
    invitation_id = _seed_private_invitation(app)

    response = client.post(
        "/invite/landing-page-test-token/open",
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("/dashboard")
    assert "tab=welcome" in location
    assert "login=success" in location

    with client.session_transaction() as session:
        assert session["invitation_id"] == invitation_id


def test_invalid_private_link_does_not_create_session(client):
    response = client.get("/invite/not-a-valid-token")

    assert response.status_code == 404

    with client.session_transaction() as session:
        assert session.get("invitation_id") is None
