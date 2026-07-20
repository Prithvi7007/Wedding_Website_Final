from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import String, cast, func, or_, select

from app.extensions import db
from app.models import AdminAuditLog


@dataclass(frozen=True)
class AuditFilters:
    query: str
    action: str
    entity_type: str
    page: int


def normalize_audit_filters(args: Any) -> AuditFilters:
    query = str(args.get("q", "")).strip()
    action = str(args.get("action", "")).strip()
    entity_type = str(args.get("entity_type", "")).strip()

    try:
        page = max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    return AuditFilters(
        query=query,
        action=action,
        entity_type=entity_type,
        page=page,
    )


def audit_list(filters: AuditFilters):
    statement = select(AdminAuditLog)

    if filters.query:
        pattern = f"%{filters.query}%"
        statement = statement.where(
            or_(
                cast(AdminAuditLog.audit_id, String).ilike(pattern),
                AdminAuditLog.action.ilike(pattern),
                AdminAuditLog.entity_type.ilike(pattern),
                AdminAuditLog.entity_id.ilike(pattern),
                AdminAuditLog.request_id.ilike(pattern),
                AdminAuditLog.remote_addr.ilike(pattern),
            )
        )

    if filters.action:
        statement = statement.where(
            AdminAuditLog.action == filters.action
        )

    if filters.entity_type:
        statement = statement.where(
            AdminAuditLog.entity_type == filters.entity_type
        )

    statement = statement.order_by(
        AdminAuditLog.created_at.desc(),
        AdminAuditLog.audit_id.desc(),
    )

    return db.paginate(
        statement,
        page=filters.page,
        per_page=int(
            current_page_size()
        ),
        error_out=False,
    )


def current_page_size() -> int:
    from flask import current_app

    return int(
        current_app.config.get("ADMIN_AUDIT_PAGE_SIZE", 50)
    )


def audit_filter_options() -> tuple[list[str], list[str]]:
    action_values = (
        select(AdminAuditLog.action)
        .distinct()
        .subquery()
    )
    entity_values = (
        select(AdminAuditLog.entity_type)
        .distinct()
        .subquery()
    )

    action_statement = (
        select(action_values.c.action)
        .order_by(func.lower(action_values.c.action).asc())
    )
    entity_statement = (
        select(entity_values.c.entity_type)
        .order_by(func.lower(entity_values.c.entity_type).asc())
    )

    actions = list(db.session.scalars(action_statement).all())
    entities = list(db.session.scalars(entity_statement).all())
    return actions, entities
