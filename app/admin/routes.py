from __future__ import annotations

import hmac

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .decorators import (
    SESSION_ADMIN_AUTHENTICATED,
    admin_required,
    clear_admin_session,
    establish_admin_session,
)
from .forms import AdminLoginForm
from .services import build_dashboard_snapshot


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _password_matches(candidate: str, configured: str) -> bool:
    """Compare the configured secret without leaking timing information."""
    return hmac.compare_digest(
        candidate.encode("utf-8"),
        configured.encode("utf-8"),
    )


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get(SESSION_ADMIN_AUTHENTICATED) is True:
        return redirect(url_for("admin.dashboard"))

    form = AdminLoginForm()
    configured_password = str(
        current_app.config.get("ADMIN_PASSWORD", "")
    )

    if not configured_password:
        current_app.logger.error(
            "Admin login is disabled because WEDDING_ADMIN_PASSWORD "
            "is not configured."
        )
        return render_template(
            "admin/login.html",
            form=form,
            configuration_error=True,
        ), 503

    if form.validate_on_submit():
        if _password_matches(
            form.password.data or "",
            configured_password,
        ):
            establish_admin_session()
            current_app.logger.info(
                "Admin login succeeded request_id=%s remote_addr=%s",
                getattr(g, "request_id", "-"),
                request.remote_addr or "-",
            )
            flash("Welcome to the wedding admin portal.", "success")
            return redirect(url_for("admin.dashboard"))

        current_app.logger.warning(
            "Admin login rejected request_id=%s remote_addr=%s",
            getattr(g, "request_id", "-"),
            request.remote_addr or "-",
        )
        flash("The administrator password was not accepted.", "error")

    return render_template(
        "admin/login.html",
        form=form,
        configuration_error=False,
    )


@admin_bp.post("/logout")
@admin_required
def logout():
    current_app.logger.info(
        "Admin logout request_id=%s remote_addr=%s",
        getattr(g, "request_id", "-"),
        request.remote_addr or "-",
    )
    clear_admin_session()
    flash("You have been signed out.", "success")
    return redirect(url_for("admin.login"))


@admin_bp.get("")
@admin_required
def dashboard():
    snapshot = build_dashboard_snapshot()
    return render_template(
        "admin/dashboard.html",
        **snapshot,
    )
