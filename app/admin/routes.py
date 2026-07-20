from __future__ import annotations

import hmac

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    Response,
    session,
    url_for,
)

from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP

from .decorators import (
    SESSION_ADMIN_AUTHENTICATED,
    admin_required,
    clear_admin_session,
    establish_admin_session,
)
from .forms import AdminLoginForm, AdminRSVPForm, InvitationForm
from .invitation_queries import (
    all_events,
    invitation_by_id,
    invitation_list,
    normalize_filters,
)
from .invitation_services import (
    apply_invitation_form,
    event_state_for_invitation,
    generate_unique_invite_token,
    permission_values_from_existing,
    permission_values_from_request,
    private_invitation_url,
    sync_permissions,
    validate_permission_changes,
)
from .rsvp_queries import (
    all_rsvp_rows,
    normalize_rsvp_filters,
    rsvp_list,
    rsvp_summary,
)
from .rsvp_services import (
    apply_rsvp_form,
    rsvp_csv,
    rsvp_for_permission,
    validate_rsvp_form,
)
from .services import build_dashboard_snapshot


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _password_matches(candidate: str, configured: str) -> bool:
    return hmac.compare_digest(
        candidate.encode("utf-8"),
        configured.encode("utf-8"),
    )


def _get_invitation_or_404(invitation_id: int) -> Invitation:
    invitation = invitation_by_id(invitation_id)
    if invitation is None:
        abort(404)
    return invitation


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


@admin_bp.get("/invitations")
@admin_required
def invitations():
    filters = normalize_filters(request.args)
    events = all_events()
    pagination = invitation_list(filters)

    return render_template(
        "admin/invitations/list.html",
        events=events,
        filters=filters,
        pagination=pagination,
    )


@admin_bp.route("/invitations/new", methods=["GET", "POST"])
@admin_required
def invitation_new():
    events = all_events()
    form = InvitationForm()

    if request.method == "POST":
        permission_values, permission_errors = (
            permission_values_from_request(events)
        )
    else:
        permission_values = permission_values_from_existing(events, None)
        permission_errors = []

    if form.validate_on_submit() and not permission_errors:
        invitation = Invitation(
            first_name="",
            display_name="",
            invite_token=generate_unique_invite_token(),
        )
        apply_invitation_form(invitation, form)

        try:
            db.session.add(invitation)
            db.session.flush()
            sync_permissions(invitation, events, permission_values)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "Admin failed to create invitation request_id=%s",
                getattr(g, "request_id", "-"),
            )
            flash(
                "The invitation could not be created. No changes were saved.",
                "error",
            )
        else:
            current_app.logger.info(
                "Admin created invitation invitation_id=%s request_id=%s",
                invitation.invitation_id,
                getattr(g, "request_id", "-"),
            )
            flash("Invitation created successfully.", "success")
            return redirect(
                url_for(
                    "admin.invitation_detail",
                    invitation_id=invitation.invitation_id,
                )
            )

    for error in permission_errors:
        flash(error, "error")

    return render_template(
        "admin/invitations/form.html",
        form=form,
        events=events,
        permission_values=permission_values,
        invitation=None,
        page_title="Add Invitation",
        submit_label="Create Invitation",
    )


@admin_bp.get("/invitations/<int:invitation_id>")
@admin_required
def invitation_detail(invitation_id: int):
    invitation = _get_invitation_or_404(invitation_id)
    events = all_events()
    permissions, rsvps = event_state_for_invitation(invitation)

    return render_template(
        "admin/invitations/detail.html",
        invitation=invitation,
        events=events,
        permissions=permissions,
        rsvps=rsvps,
        private_url=private_invitation_url(invitation),
    )


@admin_bp.route(
    "/invitations/<int:invitation_id>/edit",
    methods=["GET", "POST"],
)
@admin_required
def invitation_edit(invitation_id: int):
    invitation = _get_invitation_or_404(invitation_id)
    events = all_events()

    if request.method == "POST":
        form = InvitationForm()
        permission_values, permission_errors = (
            permission_values_from_request(events)
        )
        permission_errors.extend(
            validate_permission_changes(
                invitation,
                events,
                permission_values,
            )
        )
    else:
        form = InvitationForm(obj=invitation)
        permission_values = permission_values_from_existing(
            events,
            invitation,
        )
        permission_errors = []

    if form.validate_on_submit() and not permission_errors:
        apply_invitation_form(invitation, form)

        try:
            sync_permissions(invitation, events, permission_values)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "Admin failed to update invitation invitation_id=%s "
                "request_id=%s",
                invitation.invitation_id,
                getattr(g, "request_id", "-"),
            )
            flash(
                "The invitation could not be updated. No changes were saved.",
                "error",
            )
        else:
            current_app.logger.info(
                "Admin updated invitation invitation_id=%s request_id=%s",
                invitation.invitation_id,
                getattr(g, "request_id", "-"),
            )
            flash("Invitation updated successfully.", "success")
            return redirect(
                url_for(
                    "admin.invitation_detail",
                    invitation_id=invitation.invitation_id,
                )
            )

    for error in permission_errors:
        flash(error, "error")

    return render_template(
        "admin/invitations/form.html",
        form=form,
        events=events,
        permission_values=permission_values,
        invitation=invitation,
        page_title="Edit Invitation",
        submit_label="Save Changes",
    )


@admin_bp.post(
    "/invitations/<int:invitation_id>/toggle-active"
)
@admin_required
def invitation_toggle_active(invitation_id: int):
    invitation = _get_invitation_or_404(invitation_id)
    invitation.is_active = not invitation.is_active

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Admin failed to toggle invitation invitation_id=%s",
            invitation.invitation_id,
        )
        flash("The invitation status could not be changed.", "error")
    else:
        state = "activated" if invitation.is_active else "deactivated"
        current_app.logger.info(
            "Admin %s invitation invitation_id=%s request_id=%s",
            state,
            invitation.invitation_id,
            getattr(g, "request_id", "-"),
        )
        flash(f"Invitation {state}.", "success")

    return redirect(
        url_for(
            "admin.invitation_detail",
            invitation_id=invitation.invitation_id,
        )
    )


@admin_bp.post(
    "/invitations/<int:invitation_id>/regenerate-token"
)
@admin_required
def invitation_regenerate_token(invitation_id: int):
    invitation = _get_invitation_or_404(invitation_id)

    if request.form.get("confirm_regenerate") != "1":
        flash(
            "Confirm that you understand the previous private link "
            "will stop working.",
            "warning",
        )
        return redirect(
            url_for(
                "admin.invitation_detail",
                invitation_id=invitation.invitation_id,
            )
        )

    invitation.invite_token = generate_unique_invite_token()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Admin failed to regenerate token invitation_id=%s",
            invitation.invitation_id,
        )
        flash("The private invitation link could not be regenerated.", "error")
    else:
        current_app.logger.info(
            "Admin regenerated token invitation_id=%s request_id=%s",
            invitation.invitation_id,
            getattr(g, "request_id", "-"),
        )
        flash(
            "A new private link was created. The previous link no longer works.",
            "success",
        )

    return redirect(
        url_for(
            "admin.invitation_detail",
            invitation_id=invitation.invitation_id,
        )
    )



@admin_bp.get("/rsvps")
@admin_required
def rsvps():
    filters = normalize_rsvp_filters(request.args)
    events = all_events()
    pagination = rsvp_list(filters)
    summary = rsvp_summary(filters)

    return render_template(
        "admin/rsvps/list.html",
        events=events,
        filters=filters,
        pagination=pagination,
        summary=summary,
    )


@admin_bp.get("/rsvps/export.csv")
@admin_required
def rsvps_export():
    filters = normalize_rsvp_filters(request.args)
    rows = all_rsvp_rows(filters)
    content = rsvp_csv(rows)

    current_app.logger.info(
        "Admin exported RSVPs row_count=%s request_id=%s",
        len(rows),
        getattr(g, "request_id", "-"),
    )

    return Response(
        content,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                "attachment; filename=wedding-rsvps.csv"
            )
        },
    )


@admin_bp.route(
    "/rsvps/invitation/<int:invitation_id>/event/<event_id>/edit",
    methods=["GET", "POST"],
)
@admin_required
def rsvp_edit(invitation_id: int, event_id: str):
    permission = db.session.get(
        InvitationEventPermission,
        (invitation_id, event_id),
    )
    if permission is None:
        abort(404)

    invitation = db.session.get(Invitation, invitation_id)
    event = db.session.get(Event, event_id)
    if invitation is None or event is None:
        abort(404)

    rsvp = rsvp_for_permission(invitation_id, event_id)

    if request.method == "POST":
        form = AdminRSVPForm()
    else:
        form = AdminRSVPForm(obj=rsvp)
        if rsvp is None:
            form.attending.data = "Yes"
            form.guest_count.data = 1
            form.notes.data = ""

    validation_errors: list[str] = []
    if form.validate_on_submit():
        validation_errors = validate_rsvp_form(
            form,
            permission.max_guests,
        )

        if not validation_errors:
            created = rsvp is None
            if rsvp is None:
                rsvp = RSVP(
                    invitation_id=invitation_id,
                    event_id=event_id,
                    attending="Yes",
                    guest_count=0,
                )
                db.session.add(rsvp)

            apply_rsvp_form(rsvp, form)

            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                current_app.logger.exception(
                    "Admin failed to save RSVP invitation_id=%s "
                    "event_id=%s request_id=%s",
                    invitation_id,
                    event_id,
                    getattr(g, "request_id", "-"),
                )
                flash(
                    "The RSVP could not be saved. No changes were made.",
                    "error",
                )
            else:
                action = "created" if created else "updated"
                current_app.logger.info(
                    "Admin %s RSVP invitation_id=%s event_id=%s "
                    "request_id=%s",
                    action,
                    invitation_id,
                    event_id,
                    getattr(g, "request_id", "-"),
                )
                flash("RSVP saved successfully.", "success")
                return redirect(
                    url_for(
                        "admin.invitation_detail",
                        invitation_id=invitation_id,
                    )
                )

    for error in validation_errors:
        flash(error, "error")

    return render_template(
        "admin/rsvps/form.html",
        form=form,
        invitation=invitation,
        event=event,
        permission=permission,
        rsvp=rsvp,
    )


@admin_bp.post("/rsvps/<int:rsvp_id>/clear")
@admin_required
def rsvp_clear(rsvp_id: int):
    rsvp = db.session.get(RSVP, rsvp_id)
    if rsvp is None:
        abort(404)

    invitation_id = rsvp.invitation_id
    event_id = rsvp.event_id

    if request.form.get("confirm_clear") != "1":
        flash("Confirm that you want to clear this RSVP.", "warning")
        return redirect(
            url_for(
                "admin.invitation_detail",
                invitation_id=invitation_id,
            )
        )

    try:
        db.session.delete(rsvp)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Admin failed to clear RSVP rsvp_id=%s request_id=%s",
            rsvp_id,
            getattr(g, "request_id", "-"),
        )
        flash("The RSVP could not be cleared.", "error")
    else:
        current_app.logger.info(
            "Admin cleared RSVP rsvp_id=%s invitation_id=%s "
            "event_id=%s request_id=%s",
            rsvp_id,
            invitation_id,
            event_id,
            getattr(g, "request_id", "-"),
        )
        flash(
            "RSVP cleared. The invitation now shows no response "
            "for that event.",
            "success",
        )

    return redirect(
        url_for(
            "admin.invitation_detail",
            invitation_id=invitation_id,
        )
    )
