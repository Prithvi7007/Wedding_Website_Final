from __future__ import annotations

from typing import Any

from sqlalchemy import and_, case, distinct, exists, func, select

from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP


def _integer_scalar(statement) -> int:
    return int(db.session.scalar(statement) or 0)


def dashboard_totals() -> dict[str, int]:
    """Return all dashboard headline totals with one aggregate query."""
    normalized_status = func.lower(func.trim(RSVP.attending))

    statement = (
        select(
            func.count(
                distinct(Invitation.invitation_id)
            ).label("total_active_invitations"),
            func.count(
                distinct(RSVP.invitation_id)
            ).label("responded_invitations"),
            func.coalesce(
                func.sum(
                    case(
                        (normalized_status == "yes", RSVP.guest_count),
                        else_=0,
                    )
                ),
                0,
            ).label("attending_guests"),
            func.coalesce(
                func.sum(
                    case(
                        (normalized_status == "no", 1),
                        else_=0,
                    )
                ),
                0,
            ).label("declined_responses"),
            func.coalesce(
                func.sum(
                    case(
                        (normalized_status == "maybe", 1),
                        else_=0,
                    )
                ),
                0,
            ).label("maybe_responses"),
        )
        .select_from(Invitation)
        .outerjoin(
            RSVP,
            RSVP.invitation_id == Invitation.invitation_id,
        )
        .where(Invitation.is_active.is_(True))
    )

    row = db.session.execute(statement).mappings().one()
    total_active = int(row["total_active_invitations"] or 0)
    responded = int(row["responded_invitations"] or 0)

    return {
        "total_active_invitations": total_active,
        "responded_invitations": responded,
        "no_response_invitations": max(0, total_active - responded),
        "attending_guests": int(row["attending_guests"] or 0),
        "declined_responses": int(row["declined_responses"] or 0),
        "maybe_responses": int(row["maybe_responses"] or 0),
    }


def event_metrics() -> list[dict[str, Any]]:
    """Build event summaries dynamically from the events table."""
    normalized_status = func.lower(func.trim(RSVP.attending))

    active_invitation_id = case(
        (
            Invitation.is_active.is_(True),
            Invitation.invitation_id,
        ),
        else_=None,
    )
    active_rsvp_id = case(
        (
            and_(
                Invitation.is_active.is_(True),
                RSVP.rsvp_id.is_not(None),
            ),
            RSVP.rsvp_id,
        ),
        else_=None,
    )

    statement = (
        select(
            Event.event_id,
            Event.title,
            Event.event_date,
            Event.display_order,
            func.count(distinct(active_invitation_id)).label(
                "active_invitation_count"
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            Invitation.is_active.is_(True),
                            InvitationEventPermission.max_guests,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("maximum_possible_guests"),
            func.count(distinct(active_rsvp_id)).label("response_count"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                Invitation.is_active.is_(True),
                                normalized_status == "yes",
                            ),
                            RSVP.guest_count,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("confirmed_guest_count"),
            func.count(
                distinct(
                    case(
                        (
                            and_(
                                Invitation.is_active.is_(True),
                                normalized_status == "yes",
                            ),
                            RSVP.rsvp_id,
                        ),
                        else_=None,
                    )
                )
            ).label("yes_response_count"),
            func.count(
                distinct(
                    case(
                        (
                            and_(
                                Invitation.is_active.is_(True),
                                normalized_status == "no",
                            ),
                            RSVP.rsvp_id,
                        ),
                        else_=None,
                    )
                )
            ).label("no_response_count"),
            func.count(
                distinct(
                    case(
                        (
                            and_(
                                Invitation.is_active.is_(True),
                                normalized_status == "maybe",
                            ),
                            RSVP.rsvp_id,
                        ),
                        else_=None,
                    )
                )
            ).label("maybe_response_count"),
        )
        .select_from(Event)
        .outerjoin(
            InvitationEventPermission,
            InvitationEventPermission.event_id == Event.event_id,
        )
        .outerjoin(
            Invitation,
            Invitation.invitation_id
            == InvitationEventPermission.invitation_id,
        )
        .outerjoin(
            RSVP,
            and_(
                RSVP.invitation_id
                == InvitationEventPermission.invitation_id,
                RSVP.event_id == InvitationEventPermission.event_id,
            ),
        )
        .group_by(
            Event.event_id,
            Event.title,
            Event.event_date,
            Event.display_order,
        )
        .order_by(
            Event.display_order.asc(),
            Event.event_date.asc(),
            Event.title.asc(),
        )
    )

    rows = db.session.execute(statement).mappings().all()
    return [dict(row) for row in rows]


def recent_rsvp_activity(limit: int = 12) -> list[dict[str, Any]]:
    statement = (
        select(
            RSVP.rsvp_id,
            RSVP.attending,
            RSVP.guest_count,
            RSVP.notes,
            RSVP.updated_at,
            Invitation.invitation_id,
            Invitation.display_name,
            Invitation.first_name,
            Invitation.last_name,
            Event.event_id,
            Event.title.label("event_title"),
        )
        .join(
            Invitation,
            Invitation.invitation_id == RSVP.invitation_id,
        )
        .join(
            Event,
            Event.event_id == RSVP.event_id,
        )
        .where(Invitation.is_active.is_(True))
        .order_by(
            RSVP.updated_at.desc(),
            RSVP.rsvp_id.desc(),
        )
        .limit(limit)
    )

    rows = db.session.execute(statement).mappings().all()
    return [dict(row) for row in rows]


def invitations_without_any_response(
    limit: int = 12,
) -> list[dict[str, Any]]:
    has_rsvp = exists(
        select(RSVP.rsvp_id).where(
            RSVP.invitation_id == Invitation.invitation_id
        )
    )

    statement = (
        select(
            Invitation.invitation_id,
            Invitation.display_name,
            Invitation.first_name,
            Invitation.last_name,
            Invitation.represent_side,
            Invitation.guest_group,
            Invitation.created_at,
        )
        .where(
            Invitation.is_active.is_(True),
            ~has_rsvp,
        )
        .order_by(
            func.lower(Invitation.display_name).asc(),
            Invitation.invitation_id.asc(),
        )
        .limit(limit)
    )

    rows = db.session.execute(statement).mappings().all()
    return [dict(row) for row in rows]
