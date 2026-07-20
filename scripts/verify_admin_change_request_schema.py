from __future__ import annotations

from sqlalchemy import inspect

from app import create_app
from app.extensions import db


REQUIRED_TABLE = "admin_change_requests"
REQUIRED_COLUMNS = {
    "change_request_id",
    "request_type",
    "status",
    "requested_by",
    "requested_by_display_name",
    "invitation_id",
    "event_id",
    "request_note",
    "current_state",
    "proposed_state",
    "review_note",
    "reviewed_by",
    "created_at",
    "reviewed_at",
}


def main() -> None:
    app = create_app()

    with app.app_context():
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())

        if REQUIRED_TABLE not in tables:
            raise RuntimeError(
                f"Missing change-request table: {REQUIRED_TABLE}"
            )

        columns = {
            column["name"]
            for column in inspector.get_columns(REQUIRED_TABLE)
        }
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise RuntimeError(
                "Change-request schema is missing columns: "
                + ", ".join(missing)
            )

        print(
            "Admin change-request schema verified: "
            f"{REQUIRED_TABLE} ({len(columns)} columns)."
        )


if __name__ == "__main__":
    main()
