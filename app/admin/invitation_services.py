from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Iterable

from flask import current_app, request
from sqlalchemy import select

from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP


@dataclass(frozen=True)
class PermissionInput:
    allowed: bool
    max_guests: int


def _optional_text(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def apply_invitation_form(invitation: Invitation, form) -> None:
    invitation.first_name = (form.first_name.data or "").strip()
    invitation.last_name = _optional_text(form.last_name.data)
    invitation.partner_name = _optional_text(form.partner_name.data)
    invitation.display_name = (form.display_name.data or "").strip()
    invitation.represent_side = _optional_text(form.represent_side.data)
    invitation.guest_group = _optional_text(form.guest_group.data)
    invitation.email = _optional_text(form.email.data)
    if invitation.email:
        invitation.email = invitation.email.lower()
    invitation.phone = _optional_text(form.phone.data)
    invitation.message = _optional_text(form.message.data)
    invitation.invite_message = _optional_text(form.invite_message.data)
    invitation.is_active = bool(form.is_active.data)


def generate_unique_invite_token() -> str:
    for _ in range(20):
        token = secrets.token_urlsafe(24)
        exists_statement = select(Invitation.invitation_id).where(
            Invitation.invite_token == token
        )
        if db.session.scalar(exists_statement) is None:
            return token
    raise RuntimeError("Could not generate a unique invitation token.")


def private_invitation_url(invitation: Invitation) -> str:
    configured_base = str(
        current_app.config.get("PUBLIC_BASE_URL", "")
    ).strip()
    base_url = configured_base.rstrip("/") or request.url_root.rstrip("/")
    return f"{base_url}/invite/{invitation.invite_token}"


def permission_field_name(event_id: str, suffix: str) -> str:
    return f"event__{event_id}__{suffix}"


def permission_values_from_existing(
    events: Iterable[Event],
    invitation: Invitation | None,
) -> dict[str, PermissionInput]:
    existing = {}
    if invitation is not None:
        existing = {
            permission.event_id: permission
            for permission in invitation.permissions
        }

    values: dict[str, PermissionInput] = {}
    for event in events:
        permission = existing.get(event.event_id)
        values[event.event_id] = PermissionInput(
            allowed=permission is not None,
            max_guests=permission.max_guests if permission else 1,
        )
    return values


def permission_values_from_request(
    events: Iterable[Event],
) -> tuple[dict[str, PermissionInput], list[str]]:
    values: dict[str, PermissionInput] = {}
    errors: list[str] = []

    for event in events:
        allowed = (
            request.form.get(
                permission_field_name(event.event_id, "allowed")
            )
            == "1"
        )
        raw_max = request.form.get(
            permission_field_name(event.event_id, "max_guests"),
            "1",
        )

        try:
            max_guests = int(raw_max)
        except (TypeError, ValueError):
            max_guests = 0

        if allowed and max_guests < 1:
            errors.append(
                f"{event.title}: maximum guests must be at least 1."
            )

        values[event.event_id] = PermissionInput(
            allowed=allowed,
            max_guests=max_guests if max_guests > 0 else 1,
        )

    return values, errors


def validate_permission_changes(
    invitation: Invitation | None,
    events: Iterable[Event],
    requested: dict[str, PermissionInput],
) -> list[str]:
    if invitation is None:
        return []

    errors: list[str] = []
    existing = {
        permission.event_id: permission
        for permission in invitation.permissions
    }
    rsvps = {
        rsvp.event_id: rsvp
        for rsvp in invitation.rsvps
    }

    for event in events:
        current_permission = existing.get(event.event_id)
        requested_permission = requested[event.event_id]
        rsvp = rsvps.get(event.event_id)

        if (
            current_permission is not None
            and not requested_permission.allowed
            and rsvp is not None
        ):
            errors.append(
                f"{event.title}: access cannot be removed while an RSVP "
                "exists. Clear the RSVP first."
            )
            continue

        if (
            requested_permission.allowed
            and rsvp is not None
            and rsvp.guest_count > requested_permission.max_guests
        ):
            errors.append(
                f"{event.title}: maximum guests cannot be lower than the "
                f"saved RSVP count of {rsvp.guest_count}."
            )

    return errors


def sync_permissions(
    invitation: Invitation,
    events: Iterable[Event],
    requested: dict[str, PermissionInput],
) -> None:
    existing = {
        permission.event_id: permission
        for permission in invitation.permissions
    }

    for event in events:
        requested_permission = requested[event.event_id]
        current_permission = existing.get(event.event_id)

        if requested_permission.allowed:
            if current_permission is None:
                db.session.add(
                    InvitationEventPermission(
                        invitation_id=invitation.invitation_id,
                        event_id=event.event_id,
                        max_guests=requested_permission.max_guests,
                    )
                )
            else:
                current_permission.max_guests = (
                    requested_permission.max_guests
                )
        elif current_permission is not None:
            db.session.delete(current_permission)


def event_state_for_invitation(
    invitation: Invitation,
) -> tuple[
    dict[str, InvitationEventPermission],
    dict[str, RSVP],
]:
    permissions = {
        permission.event_id: permission
        for permission in invitation.permissions
    }
    rsvps = {
        rsvp.event_id: rsvp
        for rsvp in invitation.rsvps
    }
    return permissions, rsvps
