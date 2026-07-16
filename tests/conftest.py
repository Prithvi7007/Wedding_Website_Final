import sqlite3

import pytest
from sqlalchemy import event

from app import create_app
from app.extensions import db


def _register_sqlite_functions(dbapi_connection, _connection_record):
    """Add PostgreSQL-compatible helpers used by model check constraints."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.create_function(
            "btrim",
            1,
            lambda value: value.strip() if value is not None else None,
        )


@pytest.fixture()
def app():
    app = create_app("testing")

    with app.app_context():
        sqlite_listener_added = db.engine.dialect.name == "sqlite"

        if sqlite_listener_added:
            event.listen(
                db.engine,
                "connect",
                _register_sqlite_functions,
            )

        try:
            db.create_all()
            yield app
        finally:
            db.session.remove()
            db.drop_all()

            if sqlite_listener_added:
                event.remove(
                    db.engine,
                    "connect",
                    _register_sqlite_functions,
                )


@pytest.fixture()
def client(app):
    return app.test_client()
