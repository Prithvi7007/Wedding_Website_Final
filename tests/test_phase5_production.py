import re
from pathlib import Path

from app.extensions import db
from app.models import Invitation


def _seed_and_login(client, app):
    with app.app_context():
        invitation = Invitation(
            first_name="Secure",
            last_name="Guest",
            display_name="Secure Guest",
            invite_token="phase5-private-token",
            is_active=True,
        )
        db.session.add(invitation)
        db.session.commit()
        invitation_id = invitation.invitation_id

    response = client.get("/invite/phase5-private-token")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard?login=success")

    return invitation_id


def test_dashboard_security_headers_and_private_cache(client, app):
    _seed_and_login(client, app)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store, max-age=0"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert response.headers.get("X-Request-ID")
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_csp_nonce_matches_slideshow_json_script(client, app):
    _seed_and_login(client, app)

    response = client.get("/dashboard")
    html = response.get_data(as_text=True)
    csp = response.headers["Content-Security-Policy"]

    nonce_match = re.search(r"script-src 'self' 'nonce-([^']+)'", csp)
    assert nonce_match is not None
    nonce = nonce_match.group(1)
    assert f'nonce="{nonce}"' in html


def test_asset_urls_include_release_version(client, app):
    _seed_and_login(client, app)

    response = client.get("/dashboard")
    html = response.get_data(as_text=True)

    assert "/static/css/shell.css?v=test" in html
    assert "/static/js/app.js?v=test" in html
    assert "/static/images/slideshow/DSC06660-1170.webp?v=test" in html


def test_invitation_session_does_not_store_private_token(client, app):
    invitation_id = _seed_and_login(client, app)

    with client.session_transaction() as session:
        assert session["invitation_id"] == invitation_id
        assert "invite_token" not in session
        assert session.permanent is True



def test_static_cache_policy_distinguishes_versioned_assets(client):
    versioned = client.get("/static/css/shell.css?v=test")
    unversioned = client.get("/static/js/slideshow.js")

    assert versioned.status_code == 200
    assert versioned.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert unversioned.status_code == 200
    assert unversioned.headers["Cache-Control"] == "public, no-cache"

def test_production_files_exist():
    for relative in (
        "gunicorn.conf.py",
        "deploy/systemd/wedding.service",
        "deploy/nginx/adlinprithvi.cloud.conf",
        "scripts/production_preflight.py",
        "docs/PRODUCTION_DEPLOYMENT.md",
    ):
        assert Path(relative).exists()


def test_invite_tokens_are_suppressed_from_nginx_access_logs():
    nginx = Path("deploy/nginx/adlinprithvi.cloud.conf").read_text(encoding="utf-8")
    assert "location ^~ /invite/" in nginx
    assert "access_log off;" in nginx


def test_nginx_does_not_duplicate_shared_proxy_headers():
    nginx = Path("deploy/nginx/adlinprithvi.cloud.conf").read_text(
        encoding="utf-8"
    )

    assert "proxy_set_header Host $host;" not in nginx
    assert "proxy_set_header X-Forwarded-Proto $scheme;" not in nginx
    assert "proxy_set_header X-Forwarded-Port $server_port;" not in nginx
