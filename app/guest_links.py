"""The existing shared wedding QR identity, independent of photo storage."""
from __future__ import annotations
import hmac
from urllib.parse import urlsplit
from flask import abort, current_app, url_for


def share_token() -> str:
    return str(current_app.config.get("WEDDING_PHOTO_SHARE_TOKEN", "")).strip()


def _public_base() -> str | None:
    base = str(current_app.config.get("PUBLIC_BASE_URL", "")).strip().rstrip("/")
    try:
        parsed = urlsplit(base)
    except ValueError:
        return None
    if (not parsed.netloc or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or parsed.username or parsed.password):
        return None
    if parsed.scheme != "https" and not (current_app.testing and parsed.scheme == "http"):
        return None
    return base


def guest_link_ready() -> bool:
    token = share_token()
    return (len(token) >= 24 and all(c.isalnum() or c in "-_" for c in token)
            and _public_base() is not None)


def require_guest_link(token: str) -> None:
    if not guest_link_ready() or not hmac.compare_digest(token.encode(), share_token().encode()):
        abort(404)


def public_guest_url(endpoint: str = "seating.guest_welcome") -> str | None:
    if not guest_link_ready():
        return None
    return _public_base() + url_for(endpoint, token=share_token())
