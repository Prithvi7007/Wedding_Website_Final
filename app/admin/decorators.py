from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable, TypeVar, cast

from flask import current_app, flash, redirect, session, url_for


ViewFunction = TypeVar("ViewFunction", bound=Callable[..., Any])

SESSION_ADMIN_AUTHENTICATED = "admin_authenticated"
SESSION_ADMIN_LOGIN_AT = "admin_login_at"
SESSION_ADMIN_LAST_SEEN = "admin_last_seen"


def establish_admin_session() -> None:
    """Start a fresh administrator session after successful authentication."""
    now = int(time.time())
    session.clear()
    session.permanent = True
    session[SESSION_ADMIN_AUTHENTICATED] = True
    session[SESSION_ADMIN_LOGIN_AT] = now
    session[SESSION_ADMIN_LAST_SEEN] = now


def clear_admin_session() -> None:
    """Clear all session state during administrator logout."""
    session.clear()


def admin_required(view: ViewFunction) -> ViewFunction:
    """Require a valid administrator session with an inactivity timeout."""

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        if session.get(SESSION_ADMIN_AUTHENTICATED) is not True:
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
            flash(
                "Your admin session expired. Please sign in again.",
                "warning",
            )
            return redirect(url_for("admin.login"))

        session[SESSION_ADMIN_LAST_SEEN] = now
        session.modified = True
        return view(*args, **kwargs)

    return cast(ViewFunction, wrapped)
