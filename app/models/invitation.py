from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from .permission import InvitationEventPermission
    from .rsvp import RSVP


class Invitation(db.Model):
    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("btrim(display_name) <> ''", name="invitations_display_name_not_blank"),
        CheckConstraint("btrim(invite_token) <> ''", name="invitations_invite_token_not_blank"),
    )

    invitation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    represent_side: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str | None] = mapped_column(Text)
    partner_name: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    guest_group: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    invite_token: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(),
    )
    source_key: Mapped[str | None] = mapped_column(Text, unique=True)
    invite_message: Mapped[str | None] = mapped_column(Text)

    permissions: Mapped[list["InvitationEventPermission"]] = relationship(
        back_populates="invitation",
        lazy="selectin",
    )
    rsvps: Mapped[list["RSVP"]] = relationship(
        back_populates="invitation",
        lazy="selectin",
    )
