"""Seating planning, transactional changes and explicit guest-safe results."""
from __future__ import annotations
import csv
from io import StringIO
import unicodedata
from sqlalchemy import and_, func, inspect
from sqlalchemy.exc import SQLAlchemyError
from app.admin.audit_services import record_audit
from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP, SeatingAssignment, SeatingTable


class SeatingError(ValueError):
    """A validation message suitable for the host portal."""


def schema_ready() -> bool:
    try:
        inspector = inspect(db.engine)
        return all(inspector.has_table(name) for name in ("seating_tables", "seating_assignments"))
    except SQLAlchemyError:
        return False


def normalize_name(value: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", value.casefold())
                            if not unicodedata.combining(c)).split())


def matches_name(row: dict, query: str) -> bool:
    parts = normalize_name(query).split()
    haystack = normalize_name(" ".join(str(row.get(k) or "") for k in
                                       ("display_name", "first_name", "last_name", "partner_name")))
    return bool(parts) and all(part in haystack for part in parts)


def planning_rows(event_id: str) -> list[dict]:
    rows = db.session.execute(db.select(
        Invitation.invitation_id, Invitation.display_name, Invitation.first_name,
        Invitation.last_name, Invitation.partner_name, InvitationEventPermission.max_guests,
        RSVP.attending, RSVP.guest_count, SeatingAssignment.table_id,
        SeatingTable.name.label("table_name"),
    ).select_from(Invitation).join(InvitationEventPermission, and_(
        InvitationEventPermission.invitation_id == Invitation.invitation_id,
        InvitationEventPermission.event_id == event_id,
    )).outerjoin(RSVP, and_(RSVP.invitation_id == Invitation.invitation_id, RSVP.event_id == event_id))
      .outerjoin(SeatingAssignment, and_(SeatingAssignment.invitation_id == Invitation.invitation_id,
                                        SeatingAssignment.event_id == event_id))
      .outerjoin(SeatingTable, and_(SeatingTable.table_id == SeatingAssignment.table_id,
                                   SeatingTable.event_id == event_id))
      .where(Invitation.is_active.is_(True))
      .order_by(func.lower(Invitation.display_name), Invitation.invitation_id)).mappings().all()
    result = []
    for raw in rows:
        row = dict(raw)
        row["estimated"] = row["attending"] != "Yes"
        row["party_size"] = row["max_guests"] if row["estimated"] else row["guest_count"]
        row["response_label"] = row["attending"] or "No response"
        result.append(row)
    return result


def table_summaries(event_id: str, rows: list[dict] | None = None) -> list[dict]:
    rows = planning_rows(event_id) if rows is None else rows
    saved_counts = dict(db.session.execute(db.select(SeatingAssignment.table_id, func.count())
                        .where(SeatingAssignment.event_id == event_id)
                        .group_by(SeatingAssignment.table_id)).all())
    tables = db.session.scalars(db.select(SeatingTable).where(SeatingTable.event_id == event_id)
                               .order_by(SeatingTable.table_id)).all()
    result = []
    for table in tables:
        assigned = [row for row in rows if row["table_id"] == table.table_id]
        planned = sum(row["party_size"] for row in assigned)
        result.append({"table_id": table.table_id, "name": table.name, "capacity": table.capacity,
                       "family_count": len(assigned), "saved_family_count": saved_counts.get(table.table_id, 0),
                       "planned_count": planned,
                       "estimated_count": sum(row["party_size"] for row in assigned if row["estimated"]),
                       "over_capacity": table.capacity is not None and planned > table.capacity})
    return result


def configured_events() -> list[Event]:
    return list(db.session.scalars(db.select(Event).where(db.exists(db.select(SeatingTable.table_id)
                .where(SeatingTable.event_id == Event.event_id)))
                .order_by(Event.display_order, Event.event_date, Event.title)).all())


def choose_event(events: list[Event], requested: str) -> Event | None:
    if not events:
        return None
    if requested:
        return next((event for event in events if event.event_id == requested), None)
    return next((event for event in events if "reception" in (event.event_id + " " + event.title).casefold()), events[-1])


def guest_results(event_id: str, query: str) -> list[dict]:
    if not normalize_name(query):
        return []
    # Deliberately project only names and table labels into the public template.
    return [{"family_name": row["display_name"], "table_name": row["table_name"]}
            for row in planning_rows(event_id) if matches_name(row, query)]


def paginate(items: list, raw_page, per_page: int = 25) -> dict:
    try:
        page = max(1, int(raw_page or 1))
    except (ValueError, TypeError):
        page = 1
    pages = max(1, (len(items) + per_page - 1) // per_page)
    page = min(page, pages)
    return {"items": items[(page - 1) * per_page:page * per_page], "page": page,
            "pages": pages, "total": len(items)}


def _positive_id(value) -> int:
    try:
        result = int(value)
    except (ValueError, TypeError):
        raise SeatingError("Choose a valid family or table.") from None
    if not 1 <= result <= 2147483647:
        raise SeatingError("Choose a valid family or table.")
    return result


def _capacity(value: str) -> int | None:
    if not str(value or "").strip():
        return None
    try:
        capacity = int(value)
    except (ValueError, TypeError):
        raise SeatingError("Capacity must be a whole number, or leave it blank.") from None
    if not 0 <= capacity <= 2147483647:
        raise SeatingError("Enter a valid non-negative capacity, or leave it blank.")
    return capacity


def table_snapshot(table: SeatingTable) -> dict:
    return {"table_id": table.table_id, "event_id": table.event_id,
            "name": table.name, "capacity": table.capacity}


def save_table(event_id: str, name: str, capacity: str, table: SeatingTable | None = None) -> None:
    if db.session.get(Event, event_id) is None:
        raise SeatingError("Choose a wedding event.")
    name = str(name or "").strip()
    if not name:
        raise SeatingError("Give the table a name or number.")
    duplicate = db.select(SeatingTable.table_id).where(
        SeatingTable.event_id == event_id, func.lower(SeatingTable.name) == name.lower())
    if table:
        duplicate = duplicate.where(SeatingTable.table_id != table.table_id)
    if db.session.scalar(duplicate) is not None:
        raise SeatingError("A table with this name already exists for this event.")
    before = table_snapshot(table) if table else None
    if table is None:
        table = SeatingTable(event_id=event_id, name=name)
        db.session.add(table)
    table.name, table.capacity = name, _capacity(capacity)
    db.session.flush()
    record_audit(action="seating.table.update" if before else "seating.table.create",
                 entity_type="seating_table", entity_id=str(table.table_id), before_state=before,
                 after_state=table_snapshot(table))


def assign_families(event_id: str, raw_ids: list[str], raw_table_id: str, actor: str) -> int:
    ids = list(dict.fromkeys(_positive_id(value) for value in raw_ids))
    if not ids:
        raise SeatingError("Select the families you want to update.")
    eligible = set(db.session.scalars(db.select(Invitation.invitation_id).join(InvitationEventPermission)
                   .where(Invitation.is_active.is_(True), Invitation.invitation_id.in_(ids),
                          InvitationEventPermission.event_id == event_id)).all())
    if eligible != set(ids):
        raise SeatingError("Some selected families are not active guests for this event. Refresh the list.")
    table_id = _positive_id(raw_table_id) if raw_table_id else None
    if table_id is not None:
        table = db.session.get(SeatingTable, table_id)
        if table is None or table.event_id != event_id:
            raise SeatingError("Choose a table belonging to this event.")
    for invitation_id in ids:
        assignment = db.session.get(SeatingAssignment, (invitation_id, event_id))
        before = {"table_id": assignment.table_id} if assignment else None
        if table_id is None:
            if assignment:
                db.session.delete(assignment)
        elif assignment:
            assignment.table_id, assignment.updated_by = table_id, actor
        else:
            db.session.add(SeatingAssignment(invitation_id=invitation_id, event_id=event_id,
                                            table_id=table_id, updated_by=actor))
        record_audit(action="seating.assignment.update", entity_type="seating_assignment",
                     entity_id=f"{event_id}:{invitation_id}", before_state=before,
                     after_state={"table_id": table_id} if table_id is not None else None,
                     details={"event_id": event_id, "invitation_id": invitation_id})
    return len(ids)


def delete_table(table: SeatingTable) -> int:
    before = table_snapshot(table)
    ids = list(db.session.scalars(db.select(SeatingAssignment.invitation_id)
               .where(SeatingAssignment.table_id == table.table_id)).all())
    db.session.execute(db.delete(SeatingAssignment).where(SeatingAssignment.table_id == table.table_id))
    db.session.delete(table)
    record_audit(action="seating.table.delete", entity_type="seating_table",
                 entity_id=str(before["table_id"]), before_state=before,
                 details={"unassigned_invitation_ids": ids})
    return len(ids)


def seating_csv(rows: list[dict]) -> str:
    def safe(value):
        text = str(value if value is not None else "")
        return "'" + text if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) else text
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Family", "Table", "Planned people", "RSVP", "Count type"])
    for row in rows:
        writer.writerow([safe(row["display_name"]), safe(row["table_name"] or "Unassigned"),
                         row["party_size"], row["response_label"], "Estimated" if row["estimated"] else "Confirmed"])
    return output.getvalue()
