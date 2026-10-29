"""Scan-to-share wedding photos, with a private host review inbox."""
from __future__ import annotations

import hmac
from urllib.parse import urlsplit

from flask import (
    Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
    request, send_file, url_for,
)
from werkzeug.exceptions import RequestEntityTooLarge

from app.admin.decorators import admin_write_required, current_admin_username
from app.photos.storage import (
    PhotoUploadError, get_photo, list_photos, review_photo, save_photos,
    storage_ready,
)


photos_bp = Blueprint("photos", __name__)


@photos_bp.before_request
def protect_photo_requests():
    if request.method == "POST":
        # Flask 3.1 per-request cap. Nginx requires the matching host change.
        request.max_content_length = 32 * 1024 * 1024


@photos_bp.after_request
def private_photo_responses(response):
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    return response


def _token() -> str:
    return str(current_app.config.get("WEDDING_PHOTO_SHARE_TOKEN", "")).strip()


def _public_url() -> str | None:
    base = str(current_app.config.get("PUBLIC_BASE_URL", "")).strip().rstrip("/")
    if not base:
        return None
    parsed = urlsplit(base)
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment or not parsed.netloc:
        return None
    if parsed.scheme != "https" and not (
        current_app.testing and parsed.scheme == "http"
    ):
        return None
    return base + url_for("photos.guest_upload", token=_token())


def _enabled() -> bool:
    return (
        current_app.config.get("WEDDING_PHOTO_ENABLED") is True
        and len(_token()) >= 24
        and all(character.isalnum() or character in "-_" for character in _token())
        and storage_ready()
        and _public_url() is not None
    )


def _public_access(token: str) -> None:
    if not _enabled() or not hmac.compare_digest(_token(), token):
        abort(404)


def _wants_json() -> bool:
    return request.accept_mimetypes.best == "application/json"


@photos_bp.errorhandler(RequestEntityTooLarge)
def too_large(_error):
    message = "These photos are too large together. Try uploading fewer at a time."
    if _wants_json():
        return jsonify(success=False, message=message), 413
    return render_template("photos/guest_upload.html", error=message, success=0), 413


@photos_bp.route("/photos/<token>", methods=["GET", "POST"])
def guest_upload(token: str):
    _public_access(token)
    if request.method == "GET":
        return render_template("photos/guest_upload.html", error=None, success=0)

    if request.form.get("website", "").strip():
        # Honeypot: never store a bot's attachment.
        abort(400)

    try:
        count = save_photos(
            [upload for upload in request.files.getlist("photos") if upload.filename],
            request.form.get("guest_name"),
            request.form.get("moment", "Wedding weekend"),
        )
    except PhotoUploadError as error:
        if _wants_json():
            return jsonify(success=False, message=str(error)), 400
        return render_template(
            "photos/guest_upload.html", error=str(error), success=0,
        ), 400

    if _wants_json():
        return jsonify(success=True, count=count), 201
    # Post/Redirect/Get avoids accidental duplicate uploads on refresh.
    return redirect(url_for("photos.guest_thanks", token=token, count=count), 303)


@photos_bp.get("/photos/<token>/thanks")
def guest_thanks(token: str):
    _public_access(token)
    try:
        count = max(1, min(int(request.args.get("count", "1")), 6))
    except ValueError:
        count = 1
    return render_template("photos/guest_upload.html", error=None, success=count)


@photos_bp.get("/admin/photos")
@admin_write_required
def admin_photos():
    if not _enabled():
        return render_template("photos/admin_inbox.html", enabled=False, records=[],
                               total=0, pending=0, page=1, pages=1,
                               share_url=None, show="pending")

    records = list_photos()
    active = [item for item in records if item.get("status") != "deleted"]
    show = request.args.get("show", "pending")
    if show not in ("pending", "approved", "all"):
        show = "pending"
    selected = [item for item in active if show == "all" or item.get("status") == show]

    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1
    page_size = 36
    pages = max(1, (len(selected) + page_size - 1) // page_size)
    page = min(page, pages)

    return render_template(
        "photos/admin_inbox.html",
        enabled=True, records=selected[(page - 1)*page_size:page*page_size],
        total=len(active),
        pending=sum(item.get("status") == "pending" for item in active),
        page=page, pages=pages, show=show, share_url=_public_url(),
    )


@photos_bp.get("/admin/photos/qr.svg")
@admin_write_required
def admin_qr():
    if not _enabled():
        abort(404)
    import qrcode
    from qrcode.image.svg import SvgPathImage

    code = qrcode.make(_public_url(), error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=10, border=4, image_factory=SvgPathImage)
    from io import BytesIO

    output = BytesIO()
    code.save(output)
    output.seek(0)
    return send_file(output, mimetype="image/svg+xml", download_name="wedding-photo-qr.svg")


@photos_bp.get("/admin/photos/<photo_id>/image")
@admin_write_required
def admin_photo_image(photo_id: str):
    try:
        record, path = get_photo(photo_id)
    except (FileNotFoundError, ValueError):
        abort(404)
    download = request.args.get("download") == "1"
    response = send_file(
        path,
        mimetype="image/jpeg",
        as_attachment=download,
        download_name=f"wedding-moment-{record['id'][:12]}.jpg",
        conditional=False,
        max_age=0,
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response


@photos_bp.post("/admin/photos/<photo_id>/<action>")
@admin_write_required
def admin_photo_review(photo_id: str, action: str):
    if action not in ("approve", "delete"):
        abort(404)
    try:
        review_photo(photo_id, action, actor=current_admin_username() or "host")
    except (FileNotFoundError, ValueError):
        abort(404)
    flash("Photo approved for your private collection." if action == "approve"
          else "Photo permanently removed.", "success")
    return redirect(url_for("photos.admin_photos", show="pending"))
