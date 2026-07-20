from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from flask import current_app, g, request
from sqlalchemy import delete, func, select

from app.extensions import db
from app.models import AdminLoginAttempt


@dataclass(frozen=True)
class LoginRateState:
    blocked: bool
    failed_attempts: int
    retry_after_seconds: int


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _remote_addr() -> str:
    return str(request.remote_addr or "unknown")[:120]


def _request_id() -> str | None:
    value = str(getattr(g, "request_id", "") or "")[:120]
    return value or None


def _user_agent() -> str | None:
    value = str(request.user_agent.string or "")[:500]
    return value or None


def check_login_rate_limit() -> LoginRateState:
    now = _utcnow_naive()
    max_failures = int(
        current_app.config.get("ADMIN_LOGIN_MAX_FAILURES", 5)
    )
    failure_window_seconds = int(
        current_app.config.get(
            "ADMIN_LOGIN_FAILURE_WINDOW_SECONDS",
            900,
        )
    )
    lockout_seconds = int(
        current_app.config.get("ADMIN_LOGIN_LOCKOUT_SECONDS", 1800)
    )

    window_start = now - timedelta(seconds=failure_window_seconds)
    statement = (
        select(
            func.count(AdminLoginAttempt.attempt_id),
            func.max(AdminLoginAttempt.attempted_at),
        )
        .where(
            AdminLoginAttempt.remote_addr == _remote_addr(),
            AdminLoginAttempt.succeeded.is_(False),
            AdminLoginAttempt.attempted_at >= window_start,
        )
    )
    failed_attempts, latest_failure = db.session.execute(
        statement
    ).one()

    failed_attempts = int(failed_attempts or 0)
    if failed_attempts < max_failures or latest_failure is None:
        return LoginRateState(
            blocked=False,
            failed_attempts=failed_attempts,
            retry_after_seconds=0,
        )

    blocked_until = latest_failure + timedelta(
        seconds=lockout_seconds
    )
    retry_after = max(
        0,
        int((blocked_until - now).total_seconds()),
    )

    return LoginRateState(
        blocked=retry_after > 0,
        failed_attempts=failed_attempts,
        retry_after_seconds=retry_after,
    )


def record_failed_login() -> AdminLoginAttempt:
    attempt = AdminLoginAttempt(
        remote_addr=_remote_addr(),
        succeeded=False,
        request_id=_request_id(),
        user_agent=_user_agent(),
    )
    db.session.add(attempt)
    _prune_old_attempts()
    return attempt


def record_successful_login() -> AdminLoginAttempt:
    db.session.execute(
        delete(AdminLoginAttempt).where(
            AdminLoginAttempt.remote_addr == _remote_addr(),
            AdminLoginAttempt.succeeded.is_(False),
        )
    )

    attempt = AdminLoginAttempt(
        remote_addr=_remote_addr(),
        succeeded=True,
        request_id=_request_id(),
        user_agent=_user_agent(),
    )
    db.session.add(attempt)
    _prune_old_attempts()
    return attempt


def _prune_old_attempts() -> None:
    cutoff = _utcnow_naive() - timedelta(days=30)
    db.session.execute(
        delete(AdminLoginAttempt).where(
            AdminLoginAttempt.attempted_at < cutoff
        )
    )
