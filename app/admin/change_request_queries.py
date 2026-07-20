from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select

from app.extensions import db
from app.models import AdminChangeRequest


ALLOWED_CHANGE_REQUEST_STATUSES = {
    "all",
    "pending",
    "approved",
    "rejected",
    "cancelled",
}
ALLOWED_CHANGE_REQUEST_TYPES = {"all", "invitation", "rsvp"}


@dataclass(frozen=True)
class ChangeRequestFilters:
    status: str
    request_type: str
    page: int


def normalize_change_request_filters(
    args: Any,
    *,
    default_status: str = "pending",
) -> ChangeRequestFilters:
    status = str(args.get("status", default_status)).strip().lower()
    request_type = str(args.get("type", "all")).strip().lower()

    try:
        page = max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    if status not in ALLOWED_CHANGE_REQUEST_STATUSES:
        status = default_status
    if request_type not in ALLOWED_CHANGE_REQUEST_TYPES:
        request_type = "all"

    return ChangeRequestFilters(
        status=status,
        request_type=request_type,
        page=page,
    )


def change_request_list(
    filters: ChangeRequestFilters,
    *,
    requested_by: str | None = None,
    per_page: int = 25,
):
    statement = select(AdminChangeRequest)

    if requested_by:
        statement = statement.where(
            AdminChangeRequest.requested_by == requested_by
        )

    if filters.status != "all":
        statement = statement.where(
            AdminChangeRequest.status == filters.status
        )

    if filters.request_type != "all":
        statement = statement.where(
            AdminChangeRequest.request_type == filters.request_type
        )

    statement = statement.order_by(
        AdminChangeRequest.created_at.desc(),
        AdminChangeRequest.change_request_id.desc(),
    )

    return db.paginate(
        statement,
        page=filters.page,
        per_page=per_page,
        error_out=False,
    )


def change_request_by_id(
    change_request_id: int,
) -> AdminChangeRequest | None:
    return db.session.get(AdminChangeRequest, change_request_id)


def pending_change_request_count(
    *,
    requested_by: str | None = None,
) -> int:
    statement = select(
        func.count(AdminChangeRequest.change_request_id)
    ).where(AdminChangeRequest.status == "pending")

    if requested_by:
        statement = statement.where(
            AdminChangeRequest.requested_by == requested_by
        )

    return int(db.session.scalar(statement) or 0)


def existing_pending_request(
    *,
    requested_by: str,
    request_type: str,
    invitation_id: int,
    event_id: str | None,
) -> AdminChangeRequest | None:
    statement = select(AdminChangeRequest).where(
        AdminChangeRequest.status == "pending",
        AdminChangeRequest.requested_by == requested_by,
        AdminChangeRequest.request_type == request_type,
        AdminChangeRequest.invitation_id == invitation_id,
    )

    if event_id is None:
        statement = statement.where(
            AdminChangeRequest.event_id.is_(None)
        )
    else:
        statement = statement.where(
            AdminChangeRequest.event_id == event_id
        )

    statement = statement.order_by(
        AdminChangeRequest.change_request_id.desc()
    )
    return db.session.scalar(statement)
