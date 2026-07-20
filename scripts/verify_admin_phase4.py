from __future__ import annotations

from sqlalchemy import func, inspect, select

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
        tables = set(inspect(db.engine).get_table_names())
        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            raise RuntimeError(
                "Missing Phase 4 database tables: "
                + ", ".join(missing)
            )

        audit_count = int(
            db.session.scalar(
                select(func.count(AdminAuditLog.audit_id))
            )
            or 0
        )
        attempt_count = int(
            db.session.scalar(
                select(func.count(AdminLoginAttempt.attempt_id))
            )
            or 0
        )

        print("Admin Phase 4 verification passed.")
        print(f"Audit entries: {audit_count}")
        print(f"Login attempt records: {attempt_count}")
        print(
            "Login protection: "
            f"{app.config['ADMIN_LOGIN_MAX_FAILURES']} failures / "
            f"{app.config['ADMIN_LOGIN_FAILURE_WINDOW_SECONDS']} seconds, "
            f"{app.config['ADMIN_LOGIN_LOCKOUT_SECONDS']} second lockout"
        )


if __name__ == "__main__":
    main()
