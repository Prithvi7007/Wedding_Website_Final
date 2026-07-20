from __future__ import annotations

import hashlib
from datetime import date, datetime, time
from typing import Any, Mapping

from flask import g, has_request_context, request, session

from app.extensions import db
from app.models import AdminAuditLog, Invitation, RSVP

from .decorators import (
    SESSION_ADMIN_DISPLAY_NAME,
    SESSION_ADMIN_ROLE,
    SESSION_ADMIN_SESSION_ID,
    SESSION_ADMIN_USERNAME,
)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]

    return str(value)


def _token_fingerprint(token: str | None) -> str | None:
    if not token:
        return None
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def invitation_snapshot(
    invitation: Invitation,
    *,
    permission_values: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if permission_values is None:
        permissions = [
            {
                "event_id": permission.event_id,
                "max_guests": permission.max_guests,
            }
            for permission in sorted(
                invitation.permissions,
                key=lambda item: item.event_id,
            )
        ]
    else:
        permissions = [
            {
                "event_id": event_id,
                "max_guests": value.max_guests,
            }
            for event_id, value in sorted(permission_values.items())
            if value.allowed
        ]

    return {
        "invitation_id": invitation.invitation_id,
        "represent_side": invitation.represent_side,
        "first_name": invitation.first_name,
        "last_name": invitation.last_name,
        "partner_name": invitation.partner_name,
        "display_name": invitation.display_name,
        "guest_group": invitation.guest_group,
        "message": invitation.message,
        "invite_message": invitation.invite_message,
        "email": invitation.email,
        "phone": invitation.phone,
        "is_active": invitation.is_active,
        "source_key": invitation.source_key,
        "token_fingerprint": _token_fingerprint(
            invitation.invite_token
        ),
        "permissions": permissions,
    }


def rsvp_snapshot(rsvp: RSVP) -> dict[str, Any]:
    return {
        "rsvp_id": rsvp.rsvp_id,
        "invitation_id": rsvp.invitation_id,
        "event_id": rsvp.event_id,
        "attending": rsvp.attending,
        "guest_count": rsvp.guest_count,
        "notes": rsvp.notes,
        "updated_at": _json_safe(rsvp.updated_at),
    }


def record_audit(
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> AdminAuditLog:
    request_id = None
    remote_addr = None
    user_agent = None

    if has_request_context():
        request_id = str(getattr(g, "request_id", "") or "")[:120] or None
        remote_addr = str(request.remote_addr or "")[:120] or None
        user_agent = str(request.user_agent.string or "")[:500] or None

    session_id = (
        str(session.get(SESSION_ADMIN_SESSION_ID) or "")[:64] or None
        if has_request_context()
        else None
    )

    safe_details = dict(details or {})
    if has_request_context():
        actor_username = str(
            session.get(SESSION_ADMIN_USERNAME) or ""
        )[:80] or None
        actor_display_name = str(
            session.get(SESSION_ADMIN_DISPLAY_NAME) or ""
        )[:120] or None
        actor_role = str(
            session.get(SESSION_ADMIN_ROLE) or ""
        )[:40] or None
        if actor_username:
            safe_details.setdefault("actor_username", actor_username)
        if actor_display_name:
            safe_details.setdefault("actor_display_name", actor_display_name)
        if actor_role:
            safe_details.setdefault("actor_role", actor_role)

    audit = AdminAuditLog(
        action=action.strip(),
        entity_type=entity_type.strip(),
        entity_id=(str(entity_id)[:200] if entity_id else None),
        request_id=request_id,
        session_id=session_id,
        remote_addr=remote_addr,
        user_agent=user_agent,
        before_state=_json_safe(before_state),
        after_state=_json_safe(after_state),
        details=_json_safe(safe_details) if safe_details else None,
    )
    db.session.add(audit)
    return audit
