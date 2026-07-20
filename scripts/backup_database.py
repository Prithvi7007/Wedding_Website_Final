from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


def required(values: dict[str, str | None], name: str) -> str:
    value = str(values.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required in {ENV_PATH}.")
    return value


def main() -> int:
    values = dotenv_values(ENV_PATH)

    pg_dump = shutil.which("pg_dump")
    pg_restore = shutil.which("pg_restore")
    if not pg_dump or not pg_restore:
        raise RuntimeError(
            "pg_dump and pg_restore must be installed on the VPS."
        )

    backup_dir = Path(
        os.getenv(
            "WEDDING_BACKUP_DIR",
            "/var/backups/wedding",
        )
    )
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.chmod(0o700)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    database = str(values.get("DB_NAME") or "wedding_db").strip()
    destination = backup_dir / f"{database}_{timestamp}.dump"

    environment = os.environ.copy()
    environment["PGPASSWORD"] = required(values, "DB_PASSWORD")

    command = [
        pg_dump,
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--host",
        str(values.get("DB_HOST") or "127.0.0.1"),
        "--port",
        str(values.get("DB_PORT") or "5432"),
        "--username",
        str(values.get("DB_USER") or "wedding_user"),
        "--dbname",
        database,
        "--file",
        str(destination),
    ]

    subprocess.run(
        command,
        check=True,
        env=environment,
        cwd=PROJECT_ROOT,
    )
    destination.chmod(0o600)

    subprocess.run(
        [pg_restore, "--list", str(destination)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    retention_cutoff = datetime.now(UTC) - timedelta(days=30)
    for candidate in backup_dir.glob(f"{database}_*.dump"):
        if candidate == destination:
            continue
        modified = datetime.fromtimestamp(
            candidate.stat().st_mtime,
            tz=UTC,
        )
        if modified < retention_cutoff:
            candidate.unlink()

    print(f"Verified database backup: {destination}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
