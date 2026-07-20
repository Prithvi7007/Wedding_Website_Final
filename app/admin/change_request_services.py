from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from app.extensions import db
from app.models import (
    AdminChangeRequest,
    Invitation,
    InvitationEventPermission,
    RSVP,
)

from .audit_services import (
    invitation_snapshot,
    record_audit,
    rsvp_snapshot,
)


INVITATION_CHANGE_FIELDS = (
    "first_name",
    "last_name",
    "partner_name",
    "display_name",
    "represent_side",
    "guest_group",
    "email",
    "phone",
)


class ChangeRequestError(ValueError):
    pass


class ChangeRequestConflict(ChangeRequestError):
    pass


def _optional_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _required_text(value: Any, label: str, maximum: int) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ChangeRequestError(f"{label} is required.")
    if len(normalized) > maximum:
        raise ChangeRequestError(
            f"{label} must be {maximum} characters or fewer."
        )
    return normalized


def _bounded_optional_text(
    value: Any,
    label: str,
    maximum: int,
) -> str | None:
    normalized = _optional_text(value)
    if normalized is not None and len(normalized) > maximum:
        raise ChangeRequestError(
            f"{label} must be {maximum} characters or fewer."
        )
    return normalized


def invitation_change_state(
    invitation: Invitation,
) -> dict[str, Any]:
    return {
        field: getattr(invitation, field)
        for field in INVITATION_CHANGE_FIELDS
    }


def rsvp_change_state(
    permission: InvitationEventPermission,
    rsvp: RSVP | None,
) -> dict[str, Any]:
    return {
        "max_guests": int(permission.max_guests),
        "attending": rsvp.attending if rsvp is not None else "__clear__",
        "guest_count": int(rsvp.guest_count) if rsvp is not None else 0,
        "notes": rsvp.notes if rsvp is not None else None,
    }


def invitation_proposed_state(form: Any) -> dict[str, Any]:
    return {
        "first_name": _required_text(
            form.first_name.data,
            "Primary first name",
            200,
        ),
        "last_name": _bounded_optional_text(
            form.last_name.data,
            "Last name",
            200,
        ),
        "partner_name": _bounded_optional_text(
            form.partner_name.data,
            "Partner or household member",
            250,
        ),
        "display_name": _required_text(
            form.display_name.data,
            "Invitation display name",
            300,
        ),
        "represent_side": _bounded_optional_text(
            form.represent_side.data,
            "Representing side",
            120,
        ),
        "guest_group": _bounded_optional_text(
            form.guest_group.data,
            "Guest group",
            200,
        ),
        "email": _bounded_optional_text(
            form.email.data,
            "Email",
            320,
        ),
        "phone": _bounded_optional_text(
            form.phone.data,
            "Phone",
            80,
        ),
    }


def rsvp_proposed_state(form: Any) -> dict[str, Any]:
    attending = str(form.attending.data or "").strip()
    if attending not in {"Yes", "No", "Maybe", "__clear__"}:
        raise ChangeRequestError("Select a valid RSVP response.")

    try:
        max_guests = int(form.max_guests.data)
        guest_count = int(form.guest_count.data)
    except (TypeError, ValueError) as exc:
        raise ChangeRequestError(
            "Guest limits and guest counts must be whole numbers."
        ) from exc

    if max_guests < 1 or max_guests > 100:
        raise ChangeRequestError(
            "Maximum guests must be between 1 and 100."
        )

    if attending in {"No", "__clear__"}:
        guest_count = 0

    if guest_count < 0 or guest_count > max_guests:
        raise ChangeRequestError(
            "The requested guest count cannot exceed the maximum guests."
        )

    if attending == "Yes" and guest_count < 1:
        raise ChangeRequestError(
            "An attending RSVP must include at least one guest."
        )

    notes = _bounded_optional_text(
        form.notes.data,
        "RSVP notes",
        4000,
    )

    return {
        "max_guests": max_guests,
        "attending": attending,
        "guest_count": guest_count,
        "notes": notes,
    }


def create_invitation_change_request(
    *,
    invitation: Invitation,
    form: Any,
    requested_by: str,
    requested_by_display_name: str,
) -> AdminChangeRequest:
    request_note = _required_text(
        form.request_note.data,
        "Reason for change",
        2000,
    )
    current_state = invitation_change_state(invitation)
    proposed_state = invitation_proposed_state(form)
    if current_state == proposed_state:
        raise ChangeRequestError(
            "Change at least one household value before submitting."
        )

    change_request = AdminChangeRequest(
        request_type="invitation",
        status="pending",
        requested_by=requested_by,
        requested_by_display_name=requested_by_display_name,
        invitation_id=invitation.invitation_id,
        event_id=None,
        request_note=request_note,
        current_state=current_state,
        proposed_state=proposed_state,
    )
    db.session.add(change_request)
    db.session.flush()

    record_audit(
        action="change_request.submitted",
        entity_type="change_request",
        entity_id=str(change_request.change_request_id),
        after_state={
            "status": change_request.status,
            "request_type": change_request.request_type,
            "invitation_id": invitation.invitation_id,
        },
        details={
            "requested_by": requested_by,
            "invitation_id": invitation.invitation_id,
        },
    )
    return change_request


def create_rsvp_change_request(
    *,
    invitation: Invitation,
    permission: InvitationEventPermission,
    rsvp: RSVP | None,
    form: Any,
    requested_by: str,
    requested_by_display_name: str,
) -> AdminChangeRequest:
    request_note = _required_text(
        form.request_note.data,
        "Reason for change",
        2000,
    )
    current_state = rsvp_change_state(permission, rsvp)
    proposed_state = rsvp_proposed_state(form)
    if current_state == proposed_state:
        raise ChangeRequestError(
            "Change at least one RSVP value before submitting."
        )

    change_request = AdminChangeRequest(
        request_type="rsvp",
        status="pending",
        requested_by=requested_by,
        requested_by_display_name=requested_by_display_name,
        invitation_id=invitation.invitation_id,
        event_id=permission.event_id,
        request_note=request_note,
        current_state=current_state,
        proposed_state=proposed_state,
    )
    db.session.add(change_request)
    db.session.flush()

    record_audit(
        action="change_request.submitted",
        entity_type="change_request",
        entity_id=str(change_request.change_request_id),
        after_state={
            "status": change_request.status,
            "request_type": change_request.request_type,
            "invitation_id": invitation.invitation_id,
            "event_id": permission.event_id,
        },
        details={
            "requested_by": requested_by,
            "invitation_id": invitation.invitation_id,
            "event_id": permission.event_id,
        },
    )
    return change_request


def _ensure_pending(
    change_request: AdminChangeRequest,
) -> None:
    if change_request.status != "pending":
        raise ChangeRequestError(
            "Only pending requests can be reviewed."
        )


def _apply_invitation_request(
    change_request: AdminChangeRequest,
) -> Invitation:
    invitation = db.session.get(
        Invitation,
        change_request.invitation_id,
    )
    if invitation is None:
        raise ChangeRequestError(
            "The invitation attached to this request no longer exists."
        )

    current_state = invitation_change_state(invitation)
    if current_state != change_request.current_state:
        raise ChangeRequestConflict(
            "This invitation changed after the request was submitted. "
            "Review the current record and ask the family to submit a new request."
        )

    proposed = dict(change_request.proposed_state or {})
    validated = {
        "first_name": _required_text(
            proposed.get("first_name"),
            "Primary first name",
            200,
        ),
        "last_name": _bounded_optional_text(
            proposed.get("last_name"),
            "Last name",
            200,
        ),
        "partner_name": _bounded_optional_text(
            proposed.get("partner_name"),
            "Partner or household member",
            250,
        ),
        "display_name": _required_text(
            proposed.get("display_name"),
            "Invitation display name",
            300,
        ),
        "represent_side": _bounded_optional_text(
            proposed.get("represent_side"),
            "Representing side",
            120,
        ),
        "guest_group": _bounded_optional_text(
            proposed.get("guest_group"),
            "Guest group",
            200,
        ),
        "email": _bounded_optional_text(
            proposed.get("email"),
            "Email",
            320,
        ),
        "phone": _bounded_optional_text(
            proposed.get("phone"),
            "Phone",
            80,
        ),
    }

    before_state = invitation_snapshot(invitation)
    for field, value in validated.items():
        setattr(invitation, field, value)

    record_audit(
        action="invitation.updated_from_request",
        entity_type="invitation",
        entity_id=str(invitation.invitation_id),
        before_state=before_state,
        after_state=invitation_snapshot(invitation),
        details={
            "change_request_id": change_request.change_request_id,
        },
    )
    return invitation


def _apply_rsvp_request(
    change_request: AdminChangeRequest,
) -> RSVP | None:
    permission = db.session.get(
        InvitationEventPermission,
        (
            change_request.invitation_id,
            change_request.event_id,
        ),
    )
    if permission is None:
        raise ChangeRequestError(
            "The event permission attached to this request no longer exists."
        )

    rsvp = db.session.scalar(
        db.select(RSVP).where(
            RSVP.invitation_id == change_request.invitation_id,
            RSVP.event_id == change_request.event_id,
        )
    )

    current_state = rsvp_change_state(permission, rsvp)
    if current_state != change_request.current_state:
        raise ChangeRequestConflict(
            "This RSVP changed after the request was submitted. "
            "Review the current record and ask the family to submit a new request."
        )

    proposed = dict(change_request.proposed_state or {})
    attending = str(proposed.get("attending") or "").strip()

    try:
        max_guests = int(proposed.get("max_guests"))
        guest_count = int(proposed.get("guest_count"))
    except (TypeError, ValueError) as exc:
        raise ChangeRequestError(
            "The requested guest values are invalid."
        ) from exc

    if attending not in {"Yes", "No", "Maybe", "__clear__"}:
        raise ChangeRequestError("The requested RSVP status is invalid.")
    if max_guests < 1 or max_guests > 100:
        raise ChangeRequestError(
            "Maximum guests must be between 1 and 100."
        )
    if attending in {"No", "__clear__"}:
        guest_count = 0
    if guest_count < 0 or guest_count > max_guests:
        raise ChangeRequestError(
            "The requested guest count cannot exceed the maximum guests."
        )
    if attending == "Yes" and guest_count < 1:
        raise ChangeRequestError(
            "An attending RSVP must include at least one guest."
        )

    notes = _bounded_optional_text(
        proposed.get("notes"),
        "RSVP notes",
        4000,
    )

    permission.max_guests = max_guests
    before_state = rsvp_snapshot(rsvp) if rsvp is not None else None

    if attending == "__clear__":
        if rsvp is not None:
            rsvp_id = rsvp.rsvp_id
            db.session.delete(rsvp)
            record_audit(
                action="rsvp.cleared_from_request",
                entity_type="rsvp",
                entity_id=str(rsvp_id),
                before_state=before_state,
                details={
                    "change_request_id": change_request.change_request_id,
                    "invitation_id": change_request.invitation_id,
                    "event_id": change_request.event_id,
                    "max_guests": max_guests,
                },
            )
        return None

    created = rsvp is None
    if rsvp is None:
        rsvp = RSVP(
            invitation_id=change_request.invitation_id,
            event_id=str(change_request.event_id),
            attending=attending,
            guest_count=guest_count,
            notes=notes,
        )
        db.session.add(rsvp)
    else:
        rsvp.attending = attending
        rsvp.guest_count = guest_count
        rsvp.notes = notes

    db.session.flush()
    record_audit(
        action=(
            "rsvp.created_from_request"
            if created
            else "rsvp.updated_from_request"
        ),
        entity_type="rsvp",
        entity_id=str(rsvp.rsvp_id),
        before_state=before_state,
        after_state=rsvp_snapshot(rsvp),
        details={
            "change_request_id": change_request.change_request_id,
            "invitation_id": change_request.invitation_id,
            "event_id": change_request.event_id,
            "max_guests": max_guests,
        },
    )
    return rsvp


def approve_change_request(
    change_request: AdminChangeRequest,
    *,
    reviewed_by: str,
    review_note: str | None,
) -> None:
    _ensure_pending(change_request)

    if change_request.request_type == "invitation":
        _apply_invitation_request(change_request)
    elif change_request.request_type == "rsvp":
        _apply_rsvp_request(change_request)
    else:
        raise ChangeRequestError("Unsupported change request type.")

    before_status = change_request.status
    change_request.status = "approved"
    change_request.reviewed_by = reviewed_by
    change_request.review_note = _bounded_optional_text(
        review_note,
        "Review note",
        2000,
    )
    change_request.reviewed_at = datetime.now(UTC).replace(tzinfo=None)

    record_audit(
        action="change_request.approved",
        entity_type="change_request",
        entity_id=str(change_request.change_request_id),
        before_state={"status": before_status},
        after_state={
            "status": change_request.status,
            "reviewed_by": reviewed_by,
        },
        details={
            "request_type": change_request.request_type,
            "invitation_id": change_request.invitation_id,
            "event_id": change_request.event_id,
        },
    )


def reject_change_request(
    change_request: AdminChangeRequest,
    *,
    reviewed_by: str,
    review_note: str,
) -> None:
    _ensure_pending(change_request)
    note = _required_text(
        review_note,
        "Rejection reason",
        2000,
    )

    before_status = change_request.status
    change_request.status = "rejected"
    change_request.reviewed_by = reviewed_by
    change_request.review_note = note
    change_request.reviewed_at = datetime.now(UTC).replace(tzinfo=None)

    record_audit(
        action="change_request.rejected",
        entity_type="change_request",
        entity_id=str(change_request.change_request_id),
        before_state={"status": before_status},
        after_state={
            "status": change_request.status,
            "reviewed_by": reviewed_by,
        },
        details={
            "request_type": change_request.request_type,
            "invitation_id": change_request.invitation_id,
            "event_id": change_request.event_id,
        },
    )


def cancel_change_request(
    change_request: AdminChangeRequest,
    *,
    cancelled_by: str,
) -> None:
    _ensure_pending(change_request)
    if change_request.requested_by != cancelled_by:
        raise ChangeRequestError(
            "You can only cancel a request submitted by your account."
        )

    before_status = change_request.status
    change_request.status = "cancelled"
    change_request.reviewed_by = cancelled_by
    change_request.review_note = "Cancelled by the requesting account."
    change_request.reviewed_at = datetime.now(UTC).replace(tzinfo=None)

    record_audit(
        action="change_request.cancelled",
        entity_type="change_request",
        entity_id=str(change_request.change_request_id),
        before_state={"status": before_status},
        after_state={"status": change_request.status},
        details={
            "request_type": change_request.request_type,
            "invitation_id": change_request.invitation_id,
            "event_id": change_request.event_id,
        },
    )
