from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from .assets import asset_url  # noqa: E402
from .config import CONFIG_BY_NAME, apply_environment_config, resolve_config_name  # noqa: E402
from .extensions import csrf, db, migrate  # noqa: E402
from .logging_config import configure_logging  # noqa: E402
from .security import (  # noqa: E402
    apply_response_security,
    csp_nonce,
    prepare_request_security_context,
)


def _wants_json_error() -> bool:
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes.best == "application/json"
    )


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)

    selected_name = (config_name or resolve_config_name()).lower()
    config_class = CONFIG_BY_NAME.get(selected_name)
    if config_class is None:
        raise RuntimeError(
            f"Unknown APP_CONFIG '{selected_name}'. "
            f"Expected one of: {', '.join(CONFIG_BY_NAME)}."
        )

    app.config.from_object(config_class)
    app.config["ENVIRONMENT_NAME"] = selected_name
    apply_environment_config(app, selected_name)
    configure_logging(app.config["LOG_LEVEL"])

    if app.config.get("TRUST_PROXY_HEADERS"):
        proxy_count = int(app.config.get("TRUST_PROXY_COUNT", 1))
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=proxy_count,
            x_proto=proxy_count,
            x_host=proxy_count,
            x_port=proxy_count,
        )

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from . import models  # noqa: F401
    from .dashboard.routes import dashboard_bp
    from .health.routes import health_bp
    from .invitations.routes import invitations_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(invitations_bp)
    app.register_blueprint(dashboard_bp)

    app.before_request(prepare_request_security_context)
    app.after_request(apply_response_security)

    @app.context_processor
    def inject_asset_helpers():
        return {"asset_url": asset_url, "csp_nonce": csp_nonce}

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        if _wants_json_error():
            return jsonify(success=False, message="Your page expired. Refresh and try again."), 400
        return render_template(
            "errors/generic.html",
            status_code=400,
            heading="Please refresh the page",
            message="Your secure form session expired. Refresh the invitation and try again.",
        ), 400

    @app.errorhandler(404)
    def not_found(_error):
        return render_template(
            "errors/generic.html",
            status_code=404,
            heading="Page not found",
            message="The page you requested is not available.",
        ), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error("Unhandled application error: %s", error, exc_info=True)
        if _wants_json_error():
            return jsonify(success=False, message="Something went wrong. Please try again."), 500
        return render_template(
            "errors/generic.html",
            status_code=500,
            heading="Something went wrong",
            message="Please return to your invitation and try again in a moment.",
        ), 500

    return app
