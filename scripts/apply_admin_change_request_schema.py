from __future__ import annotations

from sqlalchemy import inspect

from app import create_app
from app.extensions import db
from app.models import AdminChangeRequest


REQUIRED_TABLE = "admin_change_requests"


def main() -> None:
    app = create_app()

    with app.app_context():
        before = set(inspect(db.engine).get_table_names())
        AdminChangeRequest.__table__.create(
            bind=db.engine,
            checkfirst=True,
        )
        after = set(inspect(db.engine).get_table_names())

        if REQUIRED_TABLE not in after:
            raise RuntimeError(
                "Change-request schema creation failed. "
                f"Missing table: {REQUIRED_TABLE}"
            )

        if REQUIRED_TABLE in before:
            print(f"Already present: {REQUIRED_TABLE}")
        else:
            print(f"Created table: {REQUIRED_TABLE}")

        print("Admin change-request database schema is ready.")


if __name__ == "__main__":
    main()
