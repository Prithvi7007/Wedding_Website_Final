from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO
from typing import Any

from app.extensions import db
from app.models import RSVP


VALID_RESPONSES = {"Yes", "No", "Maybe"}


def rsvp_for_permission(
    invitation_id: int,
    event_id: str,
) -> RSVP | None:
    return db.session.scalar(
        db.select(RSVP).where(
            RSVP.invitation_id == invitation_id,
            RSVP.event_id == event_id,
        )
    )


def validate_rsvp_form(form, max_guests: int) -> list[str]:
    errors: list[str] = []
    attending = str(form.attending.data or "").strip()
    guest_count = form.guest_count.data

    if attending not in VALID_RESPONSES:
        errors.append("Select Yes, No, or Maybe.")
        return errors

    if guest_count is None:
        errors.append("Enter the total number attending.")
        return errors

    if guest_count < 0:
        errors.append("Guest count cannot be negative.")

    if attending == "Yes" and guest_count < 1:
        errors.append(
            "An attending RSVP must include at least one guest."
        )

    if guest_count > max_guests:
        errors.append(
            f"Guest count cannot exceed this invitation's limit "
            f"of {max_guests}."
        )

    return errors


def apply_rsvp_form(
    rsvp: RSVP,
    form,
) -> None:
    attending = str(form.attending.data or "").strip()
    guest_count = int(form.guest_count.data or 0)

    rsvp.attending = attending
    rsvp.guest_count = 0 if attending == "No" else guest_count
    rsvp.notes = (form.notes.data or "").strip() or None
    rsvp.updated_at = datetime.now(timezone.utc)


def _csv_safe(value: Any) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def rsvp_csv(rows: list[dict[str, Any]]) -> str:
    output = StringIO(newline="")
    writer = csv.writer(output)

    writer.writerow(
        [
            "invitation_id",
            "display_name",
            "first_name",
            "last_name",
            "partner_name",
            "guest_group",
            "email",
            "phone",
            "invitation_active",
            "event_id",
            "event_title",
            "event_date",
            "max_guests",
            "response",
            "guest_count",
            "notes",
            "updated_at",
        ]
    )

    for row in rows:
        writer.writerow(
            [
                _csv_safe(row.get("invitation_id")),
                _csv_safe(row.get("display_name")),
                _csv_safe(row.get("first_name")),
                _csv_safe(row.get("last_name")),
                _csv_safe(row.get("partner_name")),
                _csv_safe(row.get("guest_group")),
                _csv_safe(row.get("email")),
                _csv_safe(row.get("phone")),
                "Yes" if row.get("is_active") else "No",
                _csv_safe(row.get("event_id")),
                _csv_safe(row.get("event_title")),
                _csv_safe(row.get("event_date")),
                _csv_safe(row.get("max_guests")),
                _csv_safe(row.get("attending") or "No response"),
                _csv_safe(row.get("guest_count") or 0),
                _csv_safe(row.get("notes")),
                _csv_safe(row.get("updated_at")),
            ]
        )

    return output.getvalue()
