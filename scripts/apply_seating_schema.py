"""Add only the family-seating tables; never alter invitations, events or RSVPs."""
from __future__ import annotations

import re

from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateIndex
from app import create_app
from app.extensions import db
from app.models import SeatingAssignment, SeatingTable

TABLES = (SeatingTable.__table__, SeatingAssignment.__table__)
REQUIRED_NAMES = {table.name for table in TABLES}


def _verify_schema(connection) -> None:
    inspector = inspect(connection)
    expected_foreign_keys = {
        "seating_tables": {(("event_id",), "events", ("event_id",))},
        "seating_assignments": {
            (("invitation_id",), "invitations", ("invitation_id",)),
            (("table_id", "event_id"), "seating_tables", ("table_id", "event_id")),
        },
    }
    for table in TABLES:
        actual = {column["name"]: column for column in inspector.get_columns(table.name)}
        for column in table.columns:
            found = actual.get(column.name)
            if (found is None or found["type"]._type_affinity is not column.type._type_affinity
                    or (not column.nullable and found["nullable"])):
                raise RuntimeError(f"Incompatible seating schema: {table.name}.{column.name}")
        actual_pk = inspector.get_pk_constraint(table.name).get("constrained_columns") or []
        if set(actual_pk) != {column.name for column in table.primary_key.columns}:
            raise RuntimeError(f"Incompatible seating schema primary key: {table.name}")
        actual_fk = {(tuple(key["constrained_columns"]), key["referred_table"], tuple(key["referred_columns"]))
                     for key in inspector.get_foreign_keys(table.name)}
        if not expected_foreign_keys[table.name].issubset(actual_fk):
            raise RuntimeError(f"Incompatible seating schema foreign keys: {table.name}")
    unique_pairs = {tuple(key["column_names"]) for key in inspector.get_unique_constraints("seating_tables")}
    if ("table_id", "event_id") not in unique_pairs:
        raise RuntimeError("Incompatible seating schema: missing table/event unique key")
    index_name = "seating_tables_event_name_key"
    if connection.dialect.name == "sqlite":
        # SQLite omits expression indexes from its generic inspector. Compare
        # the actual DDL with our model, including uniqueness and no predicate.
        actual = connection.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name=:name"
        ), {"name": index_name}).scalar()
        index = next(index for index in SeatingTable.__table__.indexes if index.name == index_name)
        expected = str(CreateIndex(index).compile(dialect=connection.dialect))
        canonical = lambda sql: re.sub(r'[\s"]+', '', sql or '').casefold()
        valid_index = canonical(actual) == canonical(expected)
    else:
        index = next((index for index in inspector.get_indexes("seating_tables")
                      if index["name"] == index_name), {})
        expressions = index.get("expressions", index.get("column_names", []))
        canonical = lambda sql: re.sub(r'[\s"()]', '', sql or '').casefold().replace("::text", "")
        valid_index = (index.get("unique") and list(map(canonical, expressions)) == ["event_id", "lowername"]
                       and not index.get("dialect_options", {}).get("postgresql_where"))
    if not valid_index:
        raise RuntimeError("Incompatible seating schema: incorrect unique table names index")



def apply_schema(engine) -> list[str]:
    with engine.begin() as connection:
        if connection.dialect.name == "sqlite":
            # SQLite otherwise defers BEGIN until DML, leaving DDL outside the
            # transaction. Production PostgreSQL starts it automatically.
            connection.exec_driver_sql("BEGIN")
        before = set(inspect(connection).get_table_names())
        db.metadata.create_all(bind=connection, tables=list(TABLES), checkfirst=True)
        _verify_schema(connection)
        return sorted(REQUIRED_NAMES - before)


def main() -> None:
    app = create_app()
    with app.app_context():
        created = apply_schema(db.engine)
        print("Created seating tables: " + ", ".join(created) if created else "Seating tables already present.")
        print("SEATING SCHEMA: READY")


if __name__ == "__main__":
    main()
