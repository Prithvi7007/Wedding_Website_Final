from __future__ import annotations

import os
from datetime import timedelta
from urllib.parse import quote_plus


BLOCKED_SECRET_KEYS = {
    "temporary-dev-secret-key-change-this",
    "temporary-dev-secret-key-change-later",
    "generate-a-unique-64-character-secret",
}


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} environment variable is required.")
    return value


def _as_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}.")
    return value


def build_database_uri() -> str:
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "5432")
    database = os.getenv("DB_NAME", "wedding_db")
    username = os.getenv("DB_USER", "wedding_user")
    password = _required_env("DB_PASSWORD")
    return (
        "postgresql+psycopg2://"
        f"{quote_plus(username)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(database)}"
    )


class BaseConfig:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 5,
        "pool_timeout": 15,
    }
    SESSION_COOKIE_NAME = "wedding_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_REFRESH_EACH_REQUEST = True
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_SSL_STRICT = True
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    PREFERRED_URL_SCHEME = "https"
    ASSET_VERSION = "development"
    ADMIN_PASSWORD = ""
    ADMIN_SESSION_TIMEOUT_SECONDS = 1800
    ADMIN_LOGIN_MAX_FAILURES = 5
    ADMIN_LOGIN_FAILURE_WINDOW_SECONDS = 900
    ADMIN_LOGIN_LOCKOUT_SECONDS = 1800
    ADMIN_AUDIT_PAGE_SIZE = 50
    TRUST_PROXY_HEADERS = False
    LOG_LEVEL = "INFO"
    SEND_FILE_MAX_AGE_DEFAULT = 0


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    TRUST_PROXY_HEADERS = True
    SEND_FILE_MAX_AGE_DEFAULT = 31536000


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = "test-secret-key-that-is-long-enough-for-tests"
    SQLALCHEMY_DATABASE_URI = "sqlite+pysqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    WTF_CSRF_SSL_STRICT = False
    SESSION_COOKIE_SECURE = False
    ASSET_VERSION = "test"
    LOG_LEVEL = "WARNING"
    ADMIN_PASSWORD = "test-admin-password-for-testing"
    ADMIN_SESSION_TIMEOUT_SECONDS = 1800


def apply_environment_config(app, selected_name: str) -> None:
    """Load secrets only for runtime configs, never while importing tests."""
    if selected_name == "testing":
        return

    secret_key = _required_env("SECRET_KEY")
    if secret_key in BLOCKED_SECRET_KEYS or len(secret_key) < 32:
        raise RuntimeError(
            "SECRET_KEY must be a private value at least 32 characters long."
        )

    secure_cookie = _as_bool(
        "SESSION_COOKIE_SECURE",
        selected_name == "production",
    )
    if selected_name == "production" and not secure_cookie:
        raise RuntimeError("SESSION_COOKIE_SECURE must be true in production.")

    asset_version = os.getenv("ASSET_VERSION", "").strip()
    if selected_name == "production" and not asset_version:
        raise RuntimeError(
            "ASSET_VERSION is required in production. Use a release identifier "
            "such as 20260715-1 or a short Git commit hash."
        )

    admin_password = os.getenv(
        "WEDDING_ADMIN_PASSWORD",
        "",
    ).strip()

    app.config.update(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=build_database_uri(),
        SESSION_COOKIE_SECURE=secure_cookie,
        ASSET_VERSION=asset_version or "development",
        ADMIN_PASSWORD=admin_password,
        ADMIN_SESSION_TIMEOUT_SECONDS=(
            _as_int(
                "WEDDING_ADMIN_SESSION_MINUTES",
                30,
                minimum=5,
            )
            * 60
        ),
        TRUST_PROXY_HEADERS=_as_bool(
            "TRUST_PROXY_HEADERS",
            selected_name == "production",
        ),
        TRUST_PROXY_COUNT=_as_int("TRUST_PROXY_COUNT", 1, minimum=1),
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        PUBLIC_BASE_URL=os.getenv("PUBLIC_BASE_URL", "").strip(),
        ADMIN_LOGIN_MAX_FAILURES=_as_int(
            "WEDDING_ADMIN_LOGIN_MAX_FAILURES",
            5,
            minimum=2,
        ),
        ADMIN_LOGIN_FAILURE_WINDOW_SECONDS=(
            _as_int(
                "WEDDING_ADMIN_LOGIN_WINDOW_MINUTES",
                15,
                minimum=1,
            )
            * 60
        ),
        ADMIN_LOGIN_LOCKOUT_SECONDS=(
            _as_int(
                "WEDDING_ADMIN_LOCKOUT_MINUTES",
                30,
                minimum=1,
            )
            * 60
        ),
    )

    if selected_name == "production":
        public_base_url = app.config["PUBLIC_BASE_URL"]
        if public_base_url and not public_base_url.startswith("https://"):
            raise RuntimeError("PUBLIC_BASE_URL must use https:// in production.")


def resolve_config_name() -> str:
    return os.getenv("APP_CONFIG", "production").strip().lower()


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
