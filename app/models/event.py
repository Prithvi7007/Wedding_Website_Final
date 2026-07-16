from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, Text, Time, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from .permission import InvitationEventPermission
    from .rsvp import RSVP


class Event(db.Model):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("btrim(event_id) <> ''", name="events_event_id_not_blank"),
    )

    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    end_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    timezone: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="America/New_York",
        server_default=text("'America/New_York'"),
    )
    short_date: Mapped[str | None] = mapped_column(Text)
    venue_name: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    attire_image: Mapped[str | None] = mapped_column(Text)
    attire_heading: Mapped[str | None] = mapped_column(Text)
    attire_subheading: Mapped[str | None] = mapped_column(Text)
    attire: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(),
    )

    permissions: Mapped[list["InvitationEventPermission"]] = relationship(
        back_populates="event",
        lazy="selectin",
    )
    rsvps: Mapped[list["RSVP"]] = relationship(
        back_populates="event",
        lazy="selectin",
    )
