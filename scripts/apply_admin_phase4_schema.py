from __future__ import annotations

from sqlalchemy import inspect

from app import create_app
from app.extensions import db
from app.models import AdminAuditLog, AdminLoginAttempt


REQUIRED_TABLES = {
    "admin_audit_logs",
    "admin_login_attempts",
}


def main() -> None:
    app = create_app()

    with app.app_context():
        before = set(inspect(db.engine).get_table_names())

        AdminAuditLog.__table__.create(
            bind=db.engine,
            checkfirst=True,
        )
        AdminLoginAttempt.__table__.create(
            bind=db.engine,
            checkfirst=True,
        )

        after = set(inspect(db.engine).get_table_names())
        missing = sorted(REQUIRED_TABLES - after)
        if missing:
            raise RuntimeError(
                "Phase 4 schema creation failed. Missing: "
                + ", ".join(missing)
            )

        created = sorted((after - before) & REQUIRED_TABLES)
        existing = sorted(REQUIRED_TABLES - set(created))

        if created:
            print("Created Phase 4 tables: " + ", ".join(created))
        if existing:
            print("Already present: " + ", ".join(existing))

        print("Admin Phase 4 database schema is ready.")


if __name__ == "__main__":
    main()
