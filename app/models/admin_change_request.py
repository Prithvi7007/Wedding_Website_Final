from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from .event import Event
    from .invitation import Invitation


class AdminChangeRequest(db.Model):
    __tablename__ = "admin_change_requests"
    __table_args__ = (
        CheckConstraint(
            "request_type IN ('invitation', 'rsvp')",
            name="admin_change_requests_type_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="admin_change_requests_status_valid",
        ),
        CheckConstraint(
            "btrim(requested_by) <> ''",
            name="admin_change_requests_requested_by_not_blank",
        ),
        CheckConstraint(
            "btrim(request_note) <> ''",
            name="admin_change_requests_note_not_blank",
        ),
    )

    change_request_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    request_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        index=True,
    )
    requested_by: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    requested_by_display_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    invitation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("invitations.invitation_id"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("events.event_id"),
        index=True,
    )
    request_note: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    current_state: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    proposed_state: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(
        Text,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(),
        index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
    )

    invitation: Mapped["Invitation"] = relationship(lazy="joined")
    event: Mapped["Event | None"] = relationship(lazy="joined")
