from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time

from sqlalchemy import select

from app.extensions import db
from app.models import Event, InvitationEventPermission


@dataclass(frozen=True, slots=True)
class AllowedEvent:
    event_id: str
    title: str
    event_date: date
    start_time: time
    end_time: time
    timezone: str
    short_date: str | None
    venue_name: str | None
    location: str
    description: str | None
    attire_image: str | None
    attire_heading: str | None
    attire_subheading: str | None
    attire: str | None
    display_order: int
    max_guests: int


def _to_allowed_event(event: Event, max_guests: int) -> AllowedEvent:
    return AllowedEvent(
        event_id=event.event_id,
        title=event.title,
        event_date=event.event_date,
        start_time=event.start_time,
        end_time=event.end_time,
        timezone=event.timezone,
        short_date=event.short_date,
        venue_name=event.venue_name,
        location=event.location,
        description=event.description,
        attire_image=event.attire_image,
        attire_heading=event.attire_heading,
        attire_subheading=event.attire_subheading,
        attire=event.attire,
        display_order=event.display_order,
        max_guests=max_guests,
    )


class EventRepository:
    @staticmethod
    def allowed_for_invitation(invitation_id: int) -> list[AllowedEvent]:
        statement = (
            select(Event, InvitationEventPermission.max_guests)
            .join(
                InvitationEventPermission,
                InvitationEventPermission.event_id == Event.event_id,
            )
            .where(InvitationEventPermission.invitation_id == invitation_id)
            .order_by(Event.display_order)
        )

        rows = db.session.execute(statement).all()
        return [_to_allowed_event(event, max_guests) for event, max_guests in rows]

    @staticmethod
    def allowed_event_for_invitation(
        invitation_id: int,
        event_id: str,
    ) -> AllowedEvent | None:
        statement = (
            select(Event, InvitationEventPermission.max_guests)
            .join(
                InvitationEventPermission,
                InvitationEventPermission.event_id == Event.event_id,
            )
            .where(
                InvitationEventPermission.invitation_id == invitation_id,
                Event.event_id == event_id,
            )
        )
        row = db.session.execute(statement).one_or_none()
        if row is None:
            return None
        event, max_guests = row
        return _to_allowed_event(event, max_guests)
