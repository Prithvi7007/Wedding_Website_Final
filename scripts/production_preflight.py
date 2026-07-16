from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

REQUIRED_ENV = (
    "SECRET_KEY",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "ASSET_VERSION",
)

SLIDES = ("DSC06660", "DSC06692", "DSC06717", "DSC06785", "DSC06855", "DSC06882")
SLIDE_WIDTHS = (480, 768, 1170, 1600, 2048)
TRAVEL_STEMS = ("airport", "hotel", "tampa", "restaurants")
TRAVEL_WIDTHS = (480, 768, 1200)
SCHEDULE_STEMS = ("haldi", "hindu", "church")


def fail(message: str) -> None:
    print(f"FAIL: {message}")


def ok(message: str) -> None:
    print(f"OK: {message}")


def verify_environment() -> list[str]:
    failures: list[str] = []
    if os.getenv("APP_CONFIG", "").strip().lower() != "production":
        failures.append("APP_CONFIG must be production")

    for name in REQUIRED_ENV:
        if not os.getenv(name, "").strip():
            failures.append(f"{name} is missing")

    secret = os.getenv("SECRET_KEY", "")
    if secret and len(secret) < 32:
        failures.append("SECRET_KEY must be at least 32 characters")

    if os.getenv("SESSION_COOKIE_SECURE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        failures.append("SESSION_COOKIE_SECURE must be true")

    public_url = os.getenv("PUBLIC_BASE_URL", "").strip()
    if public_url and not public_url.startswith("https://"):
        failures.append("PUBLIC_BASE_URL must use https://")

    recipients = [item.strip() for item in os.getenv("RSVP_EMAIL_TO", "").split(",") if item.strip()]
    if os.getenv("RESEND_API_KEY") and not recipients:
        failures.append("RSVP_EMAIL_TO is required when RESEND_API_KEY is configured")

    return failures


def verify_assets() -> list[str]:
    missing: list[str] = []
    static = PROJECT_ROOT / "app" / "static"

    for stem in SLIDES:
        for width in SLIDE_WIDTHS:
            for extension in ("avif", "webp"):
                path = static / "images" / "slideshow" / f"{stem}-{width}.{extension}"
                if not path.exists():
                    missing.append(str(path.relative_to(PROJECT_ROOT)))

    for stem in TRAVEL_STEMS:
        for width in TRAVEL_WIDTHS:
            for extension in ("avif", "webp"):
                path = static / "images" / "travel" / f"{stem}-{width}.{extension}"
                if not path.exists():
                    missing.append(str(path.relative_to(PROJECT_ROOT)))

    for stem in SCHEDULE_STEMS:
        for layout in ("desktop", "mobile"):
            path = static / "images" / "schedule" / f"schedule-{stem}-{layout}.webp"
            if not path.exists():
                missing.append(str(path.relative_to(PROJECT_ROOT)))

    for relative in (
        "deploy/nginx/adlinprithvi.cloud.conf",
        "deploy/systemd/wedding.service",
        "gunicorn.conf.py",
    ):
        if not (PROJECT_ROOT / relative).exists():
            missing.append(relative)

    return missing


def verify_database() -> str | None:
    from app import create_app
    from app.extensions import db

    try:
        app = create_app("production")
        with app.app_context():
            db.session.execute(text("SELECT 1"))
    except Exception as exc:
        return str(exc)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Wedding V3 production preflight")
    parser.add_argument("--check-db", action="store_true", help="Also open a read-only connection check")
    args = parser.parse_args()

    failures = verify_environment()
    if failures:
        for message in failures:
            fail(message)
    else:
        ok("production environment variables")

    missing = verify_assets()
    if missing:
        for path in missing:
            fail(f"missing {path}")
    else:
        ok("responsive images and deployment files")

    if args.check_db:
        database_error = verify_database()
        if database_error:
            fail(f"database connection: {database_error}")
            failures.append(database_error)
        else:
            ok("database connection")

    if failures or missing:
        print("Production preflight failed.")
        return 1

    print("Production preflight passed. No database changes were made.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
