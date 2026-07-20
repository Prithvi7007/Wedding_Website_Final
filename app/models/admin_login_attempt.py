from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class AdminLoginAttempt(db.Model):
    __tablename__ = "admin_login_attempts"
    __table_args__ = (
        Index(
            "ix_admin_login_attempts_remote_succeeded_time",
            "remote_addr",
            "succeeded",
            "attempted_at",
        ),
    )

    attempt_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    remote_addr: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(),
        index=True,
    )
    succeeded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    request_id: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
