from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Integer, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class AdminAuditLog(db.Model):
    __tablename__ = "admin_audit_logs"
    __table_args__ = (
        CheckConstraint(
            "btrim(action) <> ''",
            name="admin_audit_logs_action_not_blank",
        ),
        CheckConstraint(
            "btrim(entity_type) <> ''",
            name="admin_audit_logs_entity_type_not_blank",
        ),
    )

    audit_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(),
        index=True,
    )
    action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    entity_id: Mapped[str | None] = mapped_column(
        Text,
        index=True,
    )
    request_id: Mapped[str | None] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(
        Text,
        index=True,
    )
    remote_addr: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
