from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any, Iterator

from sqlalchemy import String, and_, case, cast, func, or_, select

from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP


ALLOWED_RESPONSE_FILTERS = {
    "all",
    "yes",
    "no",
    "maybe",
    "no_response",
}
ALLOWED_INVITATION_STATUS_FILTERS = {"all", "active", "inactive"}
ALLOWED_RSVP_SORTS = {"name", "event", "recent", "status"}


@dataclass(frozen=True)
class RSVPListFilters:
    query: str
    response: str
    invitation_status: str
    event_id: str
    sort: str
    page: int


@dataclass
class AdminPagination:
    items: list[dict[str, Any]]
    page: int
    per_page: int
    total: int

    @property
    def pages(self) -> int:
        if self.total == 0:
            return 0
        return ceil(self.total / self.per_page)

    def iter_pages(
        self,
        left_edge: int = 2,
        left_current: int = 2,
        right_current: int = 4,
        right_edge: int = 2,
    ) -> Iterator[int | None]:
        last = 0
        for number in range(1, self.pages + 1):
            visible = (
                number <= left_edge
                or (
                    self.page - left_current - 1
                    < number
                    < self.page + right_current
                )
                or number > self.pages - right_edge
            )
            if not visible:
                continue
            if last + 1 != number:
                yield None
            yield number
            last = number


def normalize_rsvp_filters(args: Any) -> RSVPListFilters:
    query = str(args.get("q", "")).strip()
    response = str(args.get("response", "all")).strip().lower()
    invitation_status = str(
        args.get("invitation_status", "active")
    ).strip().lower()
    event_id = str(args.get("event", "")).strip()
    sort = str(args.get("sort", "recent")).strip().lower()

    try:
        page = max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    if response not in ALLOWED_RESPONSE_FILTERS:
        response = "all"
    if invitation_status not in ALLOWED_INVITATION_STATUS_FILTERS:
        invitation_status = "active"
    if sort not in ALLOWED_RSVP_SORTS:
        sort = "recent"

    return RSVPListFilters(
        query=query,
        response=response,
        invitation_status=invitation_status,
        event_id=event_id,
        sort=sort,
        page=page,
    )


def _base_statement(filters: RSVPListFilters):
    normalized_response = func.lower(func.trim(RSVP.attending))

    statement = (
        select(
            InvitationEventPermission.invitation_id,
            InvitationEventPermission.event_id,
            InvitationEventPermission.max_guests,
            Invitation.display_name,
            Invitation.first_name,
            Invitation.last_name,
            Invitation.partner_name,
            Invitation.guest_group,
            Invitation.email,
            Invitation.phone,
            Invitation.is_active,
            Event.title.label("event_title"),
            Event.event_date,
            Event.display_order,
            RSVP.rsvp_id,
            RSVP.attending,
            RSVP.guest_count,
            RSVP.notes,
            RSVP.updated_at,
        )
        .select_from(InvitationEventPermission)
        .join(
            Invitation,
            Invitation.invitation_id
            == InvitationEventPermission.invitation_id,
        )
        .join(
            Event,
            Event.event_id == InvitationEventPermission.event_id,
        )
        .outerjoin(
            RSVP,
            and_(
                RSVP.invitation_id
                == InvitationEventPermission.invitation_id,
                RSVP.event_id
                == InvitationEventPermission.event_id,
            ),
        )
    )

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
                Invitation.email.ilike(pattern),
                Invitation.phone.ilike(pattern),
                RSVP.notes.ilike(pattern),
            )
        )

    if filters.invitation_status == "active":
        statement = statement.where(Invitation.is_active.is_(True))
    elif filters.invitation_status == "inactive":
        statement = statement.where(Invitation.is_active.is_(False))

    if filters.event_id:
        statement = statement.where(
            InvitationEventPermission.event_id == filters.event_id
        )

    if filters.response == "no_response":
        statement = statement.where(RSVP.rsvp_id.is_(None))
    elif filters.response in {"yes", "no", "maybe"}:
        statement = statement.where(
            normalized_response == filters.response
        )

    if filters.sort == "name":
        statement = statement.order_by(
            func.lower(Invitation.display_name).asc(),
            Event.display_order.asc(),
            Event.event_date.asc(),
        )
    elif filters.sort == "event":
        statement = statement.order_by(
            Event.display_order.asc(),
            Event.event_date.asc(),
            func.lower(Invitation.display_name).asc(),
        )
    elif filters.sort == "status":
        statement = statement.order_by(
            case(
                (RSVP.rsvp_id.is_(None), 1),
                else_=0,
            ).asc(),
            func.lower(func.coalesce(RSVP.attending, "")).asc(),
            func.lower(Invitation.display_name).asc(),
        )
    else:
        statement = statement.order_by(
            case(
                (RSVP.updated_at.is_(None), 1),
                else_=0,
            ).asc(),
            RSVP.updated_at.desc(),
            func.lower(Invitation.display_name).asc(),
            Event.display_order.asc(),
        )

    return statement


def rsvp_list(
    filters: RSVPListFilters,
    per_page: int = 30,
) -> AdminPagination:
    statement = _base_statement(filters)
    count_statement = select(func.count()).select_from(
        statement.order_by(None).subquery()
    )
    total = int(db.session.scalar(count_statement) or 0)

    max_page = max(1, ceil(total / per_page)) if total else 1
    page = min(filters.page, max_page)
    offset = (page - 1) * per_page

    rows = (
        db.session.execute(
            statement.limit(per_page).offset(offset)
        )
        .mappings()
        .all()
    )

    return AdminPagination(
        items=[dict(row) for row in rows],
        page=page,
        per_page=per_page,
        total=total,
    )


def all_rsvp_rows(
    filters: RSVPListFilters,
) -> list[dict[str, Any]]:
    rows = db.session.execute(_base_statement(filters)).mappings().all()
    return [dict(row) for row in rows]


def rsvp_summary(filters: RSVPListFilters) -> dict[str, int]:
    rows = all_rsvp_rows(filters)
    summary = {
        "total": len(rows),
        "yes": 0,
        "no": 0,
        "maybe": 0,
        "no_response": 0,
        "confirmed_guests": 0,
    }

    for row in rows:
        attending = str(row.get("attending") or "").strip().lower()
        if not row.get("rsvp_id"):
            summary["no_response"] += 1
        elif attending == "yes":
            summary["yes"] += 1
            summary["confirmed_guests"] += int(
                row.get("guest_count") or 0
            )
        elif attending == "no":
            summary["no"] += 1
        elif attending == "maybe":
            summary["maybe"] += 1

    return summary
