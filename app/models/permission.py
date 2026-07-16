from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from .event import Event
    from .invitation import Invitation


class InvitationEventPermission(db.Model):
    __tablename__ = "invitation_event_permissions"
    __table_args__ = (
        CheckConstraint(
            "max_guests > 0",
            name="invitation_event_permissions_max_guests_positive",
        ),
    )

    invitation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("invitations.invitation_id"),
        primary_key=True,
    )
    event_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("events.event_id"),
        primary_key=True,
        index=True,
    )
    max_guests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(),
    )

    invitation: Mapped["Invitation"] = relationship(back_populates="permissions")
    event: Mapped["Event"] = relationship(back_populates="permissions")
