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
from app.photos.r2 import RemotePhotoError


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
    response.headers["Referrer-Policy"] = "no-referrer"
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


def _gallery_enabled() -> bool:
    return (
        current_app.config.get("WEDDING_PHOTO_GALLERY_ENABLED") is True
        and len(_token()) >= 24
        and all(character.isalnum() or character in "-_" for character in _token())
        and storage_ready()
        and _public_url() is not None
    )


def _public_access(token: str, *, gallery: bool = False) -> None:
    allowed = _gallery_enabled() if gallery else _enabled()
    if not allowed or not hmac.compare_digest(_token(), token):
        abort(404)


def _wants_json() -> bool:
    return request.accept_mimetypes.best == "application/json"


@photos_bp.errorhandler(RemotePhotoError)
def r2_unavailable(_error):
    message = "Photo storage is temporarily unavailable. Please try again later."
    if _wants_json():
        return jsonify(success=False, message=message), 503
    if request.endpoint == "photos.guest_upload":
        return render_template("photos/guest_upload.html", error=message, success=0,
                               gallery_enabled=_gallery_enabled()), 503
    return render_template("errors/generic.html", status_code=503,
                           heading="Photos temporarily unavailable",
                           message=message), 503


@photos_bp.errorhandler(RequestEntityTooLarge)
def too_large(_error):
    message = "These photos are too large together. Try uploading fewer at a time."
    if _wants_json():
        return jsonify(success=False, message=message), 413
    return render_template("photos/guest_upload.html", error=message, success=0,
                           gallery_enabled=_gallery_enabled()), 413


@photos_bp.route("/photos/<token>", methods=["GET", "POST"])
def guest_upload(token: str):
    _public_access(token)
    if request.method == "GET":
        return render_template("photos/guest_upload.html", error=None, success=0,
                               gallery_enabled=_gallery_enabled())

    if request.form.get("website", "").strip():
        # Honeypot: never store a bot's attachment.
        abort(400)

    try:
        if request.form.get("gallery_consent") != "yes":
            raise PhotoUploadError("Please confirm that approved photos may appear in the wedding guest gallery.")
        count = save_photos(
            [upload for upload in request.files.getlist("photos") if upload.filename],
            request.form.get("guest_name"),
            request.form.get("moment", "Wedding weekend"),
            gallery_consent=True,
        )
    except PhotoUploadError as error:
        if _wants_json():
            return jsonify(success=False, message=str(error)), 400
        return render_template(
            "photos/guest_upload.html", error=str(error), success=0,
            gallery_enabled=_gallery_enabled(),
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
    return render_template("photos/guest_upload.html", error=None, success=count,
                           gallery_enabled=_gallery_enabled())


@photos_bp.get("/photos/<token>/gallery")
def guest_gallery(token: str):
    """Only explicitly published photographs appear to QR-link holders."""
    _public_access(token, gallery=True)
    approved = [
        photo for photo in list_photos() if photo.get("status") == "approved"
        and photo.get("gallery_consent") is True and bool(photo.get("published_at"))
    ]
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1
    per_page = 24
    pages = max(1, (len(approved) + per_page - 1) // per_page)
    page = min(page, pages)
    return render_template(
        "photos/guest_gallery.html",
        photos=approved[(page - 1) * per_page:page * per_page],
        total=len(approved),
        page=page, pages=pages, token=token,
        upload_enabled=_enabled(),
    )


@photos_bp.get("/photos/<token>/gallery/<photo_id>.jpg")
def guest_gallery_image(token: str, photo_id: str):
    _public_access(token, gallery=True)
    try:
        record, path = get_photo(photo_id)
    except (FileNotFoundError, ValueError):
        abort(404)
    # Checking approval on EVERY image request protects against stale gallery
    # HTML and revocation: pending / deleted image bytes must never leak.
    if (record.get("status") != "approved" or record.get("gallery_consent") is not True
            or not record.get("published_at")):
        abort(404)
    return send_file(
        path,
        mimetype="image/jpeg",
        conditional=False,
        max_age=0,
    )


@photos_bp.get("/admin/photos")
@admin_write_required
def admin_photos():
    if not (_enabled() or _gallery_enabled()):
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
        enabled=True, upload_enabled=_enabled(), gallery_enabled=_gallery_enabled(),
        records=selected[(page - 1)*page_size:page*page_size],
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
    if action not in ("approve", "delete", "publish", "unpublish"):
        abort(404)
    try:
        review_photo(photo_id, action, actor=current_admin_username() or "host")
    except (FileNotFoundError, ValueError):
        abort(404)
    messages = {"approve": "Photo saved privately. Publish it separately to share.",
                "publish": "Photo published in the guest gallery.",
                "unpublish": "Photo removed from the guest gallery.",
                "delete": "Photo permanently removed."}
    flash(messages[action], "success")
    return redirect(url_for("photos.admin_photos", show="approved" if action in ("publish", "unpublish") else "pending"))
