from pathlib import Path

from app.extensions import db
from app.models import Invitation


def _seed_invitation(app):
    with app.app_context():
        invitation = Invitation(
            first_name="Test",
            last_name="Guest",
            display_name="Test Guest",
            invite_token="phase4-test-token",
            is_active=True,
        )
        db.session.add(invitation)
        db.session.commit()
        return invitation.invitation_id


def _login(client, app, invitation_id):
    with app.app_context():
        invitation = db.session.get(Invitation, invitation_id)
        with client.session_transaction() as session:
            session["invitation_id"] = invitation.invitation_id


def test_travel_fragment_renders_editorial_guide(client, app):
    invitation_id = _seed_invitation(app)
    _login(client, app, invitation_id)

    response = client.get("/dashboard/tab/travel")

    assert response.status_code == 200
    assert b"Travel Guide" in response.data
    assert b"Tampa International Airport" in response.data
    assert b"data-information-root" in response.data
    assert b"V3 Migration" not in response.data


def test_registry_fragment_contains_target_registry(client, app):
    invitation_id = _seed_invitation(app)
    _login(client, app, invitation_id)

    response = client.get("/dashboard/tab/registry")

    assert response.status_code == 200
    assert b"View Target Registry" in response.data
    assert b"https://www.target.com/gift-registry/gift/Adlin-Prithvi" in response.data
    assert b'rel="noopener noreferrer"' in response.data


def test_qa_fragment_uses_accessible_details(client, app):
    invitation_id = _seed_invitation(app)
    _login(client, app, invitation_id)

    response = client.get("/dashboard/tab/qa")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Questions &amp; Answers" in html
    assert 'data-qa-accordion' in html
    assert html.count('<details class="qa-item') == 9
    assert 'data-tab-name="schedule"' in html
    assert 'data-tab-name="travel"' in html


def test_phase4_assets_and_modules_exist():
    assert Path("app/static/css/information.css").exists()
    assert Path("app/static/js/information.js").exists()

    for stem in ("airport", "hotel", "tampa", "restaurants"):
        for width in (480, 768, 1200):
            assert Path(f"app/static/images/travel/{stem}-{width}.webp").exists()
            assert Path(f"app/static/images/travel/{stem}-{width}.avif").exists()


def test_information_styles_and_module_are_loaded():
    base = Path("app/templates/layouts/dashboard_base.html").read_text(encoding="utf-8")
    app_js = Path("app/static/js/app.js").read_text(encoding="utf-8")

    assert "css/information.css" in base
    assert 'from "./information.js"' in app_js
    assert "mountInformationTabs(root)" in app_js


def test_travel_grid_does_not_stretch_feature_card_across_rows():
    css = Path("app/static/css/information.css").read_text(encoding="utf-8")

    assert ".travel-story-feature {" in css
    assert "grid-column: 1 / -1;" in css
    assert "grid-row: span 2;" not in css
    assert "align-items: start;" in css
