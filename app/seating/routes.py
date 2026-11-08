"""Shared guest welcome/search pages and the existing host portal's seating tools."""
from __future__ import annotations
from io import BytesIO

from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, send_file, url_for
from sqlalchemy.exc import DataError, IntegrityError
from app.admin.decorators import admin_required, admin_write_required, current_admin_username
from app.admin.invitation_queries import all_events
from app.extensions import db
from app.guest_links import public_guest_url, require_guest_link
from app.models import SeatingTable
from app.photos.routes import _enabled as uploads_enabled, _gallery_enabled as gallery_enabled
from .services import (SeatingError, assign_families, choose_event, configured_events, delete_table,
                       guest_results, matches_name, paginate, planning_rows, save_table,
                       schema_ready, seating_csv, table_summaries)

seating_bp = Blueprint("seating", __name__)


@seating_bp.after_request
def private_seating_response(response):
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response.headers["Referrer-Policy"] = "same-origin" if request.path.startswith("/admin/") else "no-referrer"
    return response


@seating_bp.app_context_processor
def shared_guest_navigation():
    endpoints = {"photos.guest_upload", "photos.guest_thanks", "photos.guest_gallery",
                 "seating.guest_welcome", "seating.guest_find"}
    if request.endpoint not in endpoints:
        return {}
    return {"experience_token": (request.view_args or {}).get("token"),
            "experience_upload_enabled": uploads_enabled(),
            "experience_gallery_enabled": gallery_enabled()}


@seating_bp.get("/photos/<token>/welcome")
def guest_welcome(token: str):
    require_guest_link(token)
    return render_template("experience/welcome.html", seating_ready=schema_ready())


@seating_bp.get("/photos/<token>/seating")
def guest_find(token: str):
    require_guest_link(token)
    if not schema_ready():
        return render_template("experience/seating.html", ready=False, events=[], selected=None,
                               query="", results=[], page=1, pages=1, total=0), 503
    events = configured_events()
    selected = choose_event(events, request.args.get("event", ""))
    if request.args.get("event") and selected is None and events:
        abort(404)
    query = request.args.get("q", "").strip()
    matches = guest_results(selected.event_id, query) if selected else []
    pagination = paginate(matches, request.args.get("page"))
    return render_template("experience/seating.html", ready=True, events=events, selected=selected,
                           query=query, results=pagination.pop("items"), **pagination)


def _admin_view(event_id: str = "", status: int = 200):
    if not schema_ready():
        return render_template("seating/admin.html", ready=False), 503
    events = all_events()
    selected = choose_event(events, event_id or request.values.get("event", ""))
    if (event_id or request.values.get("event")) and selected is None:
        abort(404)
    rows = planning_rows(selected.event_id) if selected else []
    tables = table_summaries(selected.event_id, rows) if selected else []
    query = request.values.get("q", "").strip()
    view = request.values.get("view", "all")
    view = view if view in {"all", "assigned", "unassigned"} else "all"
    table_filter = request.args.get("table", "")
    filtered = [row for row in rows if (not query or matches_name(row, query))
                and (view == "all" or (view == "assigned") == (row["table_id"] is not None))
                and (not table_filter or str(row["table_id"]) == table_filter)]
    pagination = paginate(filtered, request.args.get("page"))
    return render_template("seating/admin.html", ready=True, events=events, selected=selected,
                           tables=tables, families=pagination.pop("items"), query=query, view=view,
                           table_filter=table_filter, family_total=len(rows),
                           assigned_count=sum(row["table_id"] is not None for row in rows),
                           share_url=public_guest_url(), **pagination), status


@seating_bp.get("/admin/seating")
@admin_required
def admin_index():
    return _admin_view()


def _perform(event_id: str, operation, success: str):
    if not schema_ready():
        return _admin_view(event_id)
    try:
        operation()
        db.session.commit()
    except SeatingError as error:
        db.session.rollback()
        flash(str(error), "warning")
        return _admin_view(event_id, 400)
    except (IntegrityError, DataError):
        db.session.rollback()
        flash("The seating plan changed or a value could not be saved. Check the details and try again.", "warning")
        return _admin_view(event_id, 400)
    flash(success, "success")
    return redirect(url_for("seating.admin_index", event=event_id,
                            view=request.form.get("view", "all"), q=request.form.get("q", "")), code=303)


@seating_bp.post("/admin/seating/tables")
@admin_write_required
def admin_create_table():
    event_id = request.form.get("event_id", "")
    return _perform(event_id, lambda: save_table(event_id, request.form.get("name", ""),
                                               request.form.get("capacity", "")), "Table added.")


def _table_or_404(table_id: int):
    table = db.session.get(SeatingTable, table_id)
    if table is None:
        abort(404)
    return table


@seating_bp.post("/admin/seating/tables/<int:table_id>/update")
@admin_write_required
def admin_update_table(table_id: int):
    if not schema_ready():
        return _admin_view()
    table = _table_or_404(table_id)
    return _perform(table.event_id, lambda: save_table(table.event_id, request.form.get("name", ""),
                                                      request.form.get("capacity", ""), table), "Table updated.")


@seating_bp.post("/admin/seating/tables/<int:table_id>/delete")
@admin_write_required
def admin_delete_table(table_id: int):
    if not schema_ready():
        return _admin_view()
    table = _table_or_404(table_id)
    return _perform(table.event_id, lambda: delete_table(table), "Table removed. Its families are now unassigned.")


@seating_bp.post("/admin/seating/assign")
@admin_write_required
def admin_assign():
    event_id = request.form.get("event_id", "")
    return _perform(event_id, lambda: assign_families(event_id, request.form.getlist("invitation_ids"),
                                                     request.form.get("table_id", ""),
                                                     current_admin_username() or "host"), "Family assignments updated.")


@seating_bp.get("/admin/seating/export.csv")
@admin_required
def admin_export():
    if not schema_ready():
        return _admin_view()
    selected = choose_event(all_events(), request.args.get("event", ""))
    if selected is None:
        abort(404)
    response = make_response("\ufeff" + seating_csv(planning_rows(selected.event_id)))
    response.mimetype = "text/csv"
    response.headers["Content-Disposition"] = 'attachment; filename="wedding-seating.csv"'
    return response


@seating_bp.get("/admin/seating/qr.svg")
@admin_required
def admin_qr():
    share_url = public_guest_url()
    if share_url is None:
        abort(404)
    import qrcode
    from qrcode.image.svg import SvgPathImage
    code = qrcode.make(share_url, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=10, border=4, image_factory=SvgPathImage)
    output = BytesIO()
    code.save(output)
    output.seek(0)
    return send_file(output, mimetype="image/svg+xml", download_name="adlin-prithvi-guest-qr.svg")
