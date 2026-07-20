from __future__ import annotations

import time
import uuid
from functools import wraps
from typing import Any, Callable, TypeVar, cast

from flask import current_app, flash, redirect, session, url_for


ViewFunction = TypeVar("ViewFunction", bound=Callable[..., Any])

SESSION_ADMIN_AUTHENTICATED = "admin_authenticated"
SESSION_ADMIN_LOGIN_AT = "admin_login_at"
SESSION_ADMIN_LAST_SEEN = "admin_last_seen"
SESSION_ADMIN_SESSION_ID = "admin_session_id"
SESSION_ADMIN_USERNAME = "admin_username"
SESSION_ADMIN_DISPLAY_NAME = "admin_display_name"
SESSION_ADMIN_ROLE = "admin_role"

ADMIN_ROLE = "admin"
VIEWER_ROLE = "viewer"


def establish_admin_session(
    *,
    username: str,
    display_name: str,
    role: str,
) -> str:
    if role not in {ADMIN_ROLE, VIEWER_ROLE}:
        raise ValueError("Unsupported portal role.")

    now = int(time.time())
    session_id = uuid.uuid4().hex

    session.clear()
    session.permanent = True
    session[SESSION_ADMIN_AUTHENTICATED] = True
    session[SESSION_ADMIN_LOGIN_AT] = now
    session[SESSION_ADMIN_LAST_SEEN] = now
    session[SESSION_ADMIN_SESSION_ID] = session_id
    session[SESSION_ADMIN_USERNAME] = username
    session[SESSION_ADMIN_DISPLAY_NAME] = display_name
    session[SESSION_ADMIN_ROLE] = role
    return session_id


def clear_admin_session() -> None:
    session.clear()


def current_admin_username() -> str | None:
    value = str(session.get(SESSION_ADMIN_USERNAME) or "").strip()
    return value or None


def current_admin_display_name() -> str | None:
    value = str(session.get(SESSION_ADMIN_DISPLAY_NAME) or "").strip()
    return value or None


def current_admin_role() -> str | None:
    value = str(session.get(SESSION_ADMIN_ROLE) or "").strip().lower()
    return value or None


def current_admin_is_full() -> bool:
    return current_admin_role() == ADMIN_ROLE


def admin_required(view: ViewFunction) -> ViewFunction:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        if session.get(SESSION_ADMIN_AUTHENTICATED) is not True:
            return redirect(url_for("admin.login"))

        username = current_admin_username()
        role = current_admin_role()
        if not username or role not in {ADMIN_ROLE, VIEWER_ROLE}:
            session.clear()
            flash("Your portal session is invalid. Please sign in again.", "warning")
            return redirect(url_for("admin.login"))

        now = int(time.time())
        timeout_seconds = int(
            current_app.config.get("ADMIN_SESSION_TIMEOUT_SECONDS", 1800)
        )
        try:
            last_seen = int(session.get(SESSION_ADMIN_LAST_SEEN, 0))
        except (TypeError, ValueError):
            last_seen = 0

        if last_seen <= 0 or now - last_seen > timeout_seconds:
            session.clear()
            flash("Your admin session expired. Please sign in again.", "warning")
            return redirect(url_for("admin.login"))

        session[SESSION_ADMIN_LAST_SEEN] = now
        session.modified = True
        return view(*args, **kwargs)

    return cast(ViewFunction, wrapped)


def admin_write_required(view: ViewFunction) -> ViewFunction:
    @admin_required
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        if not current_admin_is_full():
            flash(
                "This family account has view-only access. "
                "Only Adlin or Prithvi can make changes.",
                "warning",
            )
            return redirect(url_for("admin.dashboard"))
        return view(*args, **kwargs)

    return cast(ViewFunction, wrapped)


def admin_only(view: ViewFunction) -> ViewFunction:
    return admin_write_required(view)
