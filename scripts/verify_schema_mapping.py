"""Compare the V3 SQLAlchemy model columns with the live PostgreSQL schema.

This script is read-only. It checks table and column names only and never reads
invitation or RSVP rows.
"""

from __future__ import annotations

from sqlalchemy import inspect

from app import create_app
from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP


MODELS = [Invitation, Event, InvitationEventPermission, RSVP]


def main() -> None:
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        errors: list[str] = []

        for model in MODELS:
            table_name = model.__tablename__
            live_columns = {
                item["name"] for item in inspector.get_columns(table_name, schema="public")
            }
            model_columns = {column.name for column in model.__table__.columns}

            missing_in_model = live_columns - model_columns
            missing_in_database = model_columns - live_columns

            if missing_in_model:
                errors.append(
                    f"{table_name}: live-only columns: {sorted(missing_in_model)}"
                )
            if missing_in_database:
                errors.append(
                    f"{table_name}: model-only columns: {sorted(missing_in_database)}"
                )

            if not missing_in_model and not missing_in_database:
                print(f"OK {table_name}: {len(model_columns)} columns")

        if errors:
            raise SystemExit("\n".join(errors))

        print("Schema mapping matches all four production tables.")


if __name__ == "__main__":
    main()
