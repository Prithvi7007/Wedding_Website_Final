from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import String, cast, exists, func, or_, select

from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission


ALLOWED_STATUS_FILTERS = {"all", "active", "inactive"}
ALLOWED_SORTS = {"name", "newest", "oldest", "group"}


@dataclass(frozen=True)
class InvitationListFilters:
    query: str
    status: str
    event_id: str
    sort: str
    page: int


def normalize_filters(args: Any) -> InvitationListFilters:
    query = str(args.get("q", "")).strip()
    status = str(args.get("status", "all")).strip().lower()
    event_id = str(args.get("event", "")).strip()
    sort = str(args.get("sort", "name")).strip().lower()

    try:
        page = max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    if status not in ALLOWED_STATUS_FILTERS:
        status = "all"
    if sort not in ALLOWED_SORTS:
        sort = "name"

    return InvitationListFilters(
        query=query,
        status=status,
        event_id=event_id,
        sort=sort,
        page=page,
    )


def all_events() -> list[Event]:
    statement = select(Event).order_by(
        Event.display_order.asc(),
        Event.event_date.asc(),
        Event.title.asc(),
    )
    return list(db.session.scalars(statement).all())


def invitation_list(filters: InvitationListFilters, per_page: int = 25):
    statement = select(Invitation)

    if filters.query:
        pattern = f"%{filters.query}%"
        statement = statement.where(
            or_(
                cast(Invitation.invitation_id, String).ilike(pattern),
                Invitation.display_name.ilike(pattern),
                Invitation.first_name.ilike(pattern),
                Invitation.last_name.ilike(pattern),
                Invitation.partner_name.ilike(pattern),
                Invitation.guest_group.ilike(pattern),
                Invitation.represent_side.ilike(pattern),
                Invitation.email.ilike(pattern),
                Invitation.phone.ilike(pattern),
            )
        )

    if filters.status == "active":
        statement = statement.where(Invitation.is_active.is_(True))
    elif filters.status == "inactive":
        statement = statement.where(Invitation.is_active.is_(False))

    if filters.event_id:
        has_event_access = exists(
            select(InvitationEventPermission.invitation_id).where(
                InvitationEventPermission.invitation_id
                == Invitation.invitation_id,
                InvitationEventPermission.event_id == filters.event_id,
            )
        )
        statement = statement.where(has_event_access)

    if filters.sort == "newest":
        statement = statement.order_by(
            Invitation.created_at.desc(),
            Invitation.invitation_id.desc(),
        )
    elif filters.sort == "oldest":
        statement = statement.order_by(
            Invitation.created_at.asc(),
            Invitation.invitation_id.asc(),
        )
    elif filters.sort == "group":
        statement = statement.order_by(
            func.lower(func.coalesce(Invitation.guest_group, "")).asc(),
            func.lower(Invitation.display_name).asc(),
            Invitation.invitation_id.asc(),
        )
    else:
        statement = statement.order_by(
            func.lower(Invitation.display_name).asc(),
            Invitation.invitation_id.asc(),
        )

    return db.paginate(
        statement,
        page=filters.page,
        per_page=per_page,
        error_out=False,
    )


def invitation_by_id(invitation_id: int) -> Invitation | None:
    return db.session.get(Invitation, invitation_id)
