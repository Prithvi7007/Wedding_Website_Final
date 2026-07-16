from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from .event import Event
    from .invitation import Invitation


class RSVP(db.Model):
    __tablename__ = "rsvps"
    __table_args__ = (
        CheckConstraint(
            "attending IN ('Yes', 'No', 'Maybe')",
            name="rsvps_attending_valid",
        ),
        CheckConstraint(
            "guest_count >= 0",
            name="rsvps_guest_count_not_negative",
        ),
        UniqueConstraint(
            "invitation_id",
            "event_id",
            name="rsvps_invitation_id_event_id_key",
        ),
    )

    rsvp_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invitation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("invitations.invitation_id"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("events.event_id"),
        nullable=False,
        index=True,
    )
    attending: Mapped[str] = mapped_column(Text, nullable=False)
    guest_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    invitation: Mapped["Invitation"] = relationship(back_populates="rsvps")
    event: Mapped["Event"] = relationship(back_populates="rsvps")
