from flask import Blueprint, current_app, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db


health_bp = Blueprint("health", __name__)


@health_bp.get("/healthz")
def healthcheck():
    return jsonify(status="ok")


@health_bp.get("/readyz")
def readiness():
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Database readiness check failed")
        return jsonify(status="not_ready", database="unavailable"), 503
    return jsonify(status="ready", database="ok")
