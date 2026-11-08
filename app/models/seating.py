"""Event-specific tables and one assignment per invitation/family."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.extensions import db


class SeatingTable(db.Model):
    __tablename__ = "seating_tables"
    __table_args__ = (
        UniqueConstraint("table_id", "event_id", name="seating_tables_id_event_key"),
        CheckConstraint("btrim(name) <> ''", name="seating_tables_name_not_blank"),
        CheckConstraint("capacity IS NULL OR capacity >= 0", name="seating_tables_capacity_nonnegative"),
    )
    table_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(Text, ForeignKey("events.event_id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)


Index("seating_tables_event_name_key", SeatingTable.event_id, func.lower(SeatingTable.name), unique=True)


class SeatingAssignment(db.Model):
    __tablename__ = "seating_assignments"
    __table_args__ = (
        ForeignKeyConstraint(["table_id", "event_id"], ["seating_tables.table_id", "seating_tables.event_id"],
                             name="seating_assignments_table_event_fkey", ondelete="CASCADE"),
    )
    invitation_id: Mapped[int] = mapped_column(Integer, ForeignKey("invitations.invitation_id", ondelete="CASCADE"), primary_key=True)
    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    table_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)
