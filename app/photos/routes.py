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
    storage_ready, photo_is_shared,
)
from app.photos.r2 import RemotePhotoError


photos_bp = Blueprint("photos", __name__)


def prepare_photo_upload_limit():
    """Set the upload cap before CSRF protection reads multipart form data."""
    if request.endpoint == "photos.guest_upload" and request.method == "POST":
        # Registered at app level before csrf.init_app; blueprint hooks run
        # after CSRF has already parsed the form under the ordinary 2 MiB cap.
        request.max_content_length = 32 * 1024 * 1024


@photos_bp.after_request
def private_photo_responses(response):
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    # Secure CSRF checks require a referrer on form submissions. Same-origin
    # keeps it available to this app while suppressing it for external sites.
    form_page = request.endpoint in {"photos.guest_upload", "photos.admin_photos"}
    response.headers["Referrer-Policy"] = "same-origin" if form_page else "no-referrer"
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
            raise PhotoUploadError("Please confirm that your photos will appear immediately in the wedding guest gallery.")
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
        count = max(1, int(request.args.get("count", "1")))
    except ValueError:
        count = 1
    return render_template("photos/guest_upload.html", error=None, success=count,
                           gallery_enabled=_gallery_enabled())


@photos_bp.get("/photos/<token>/gallery")
def guest_gallery(token: str):
    """Consented uploads appear immediately, unless a host hides or deletes them."""
    _public_access(token, gallery=True)
    shared = [photo for photo in list_photos() if photo_is_shared(photo)]
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1
    per_page = 24
    pages = max(1, (len(shared) + per_page - 1) // per_page)
    page = min(page, pages)
    return render_template(
        "photos/guest_gallery.html",
        photos=shared[(page - 1) * per_page:page * per_page],
        total=len(shared),
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
    # Check on every request so hidden/deleted images disappear from stale pages.
    if not photo_is_shared(record):
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
                               total=0, shared=0, page=1, pages=1,
                               share_url=None, show="all")

    records = list_photos()
    active = [item for item in records if item.get("status") != "deleted"]
    show = request.args.get("show", "all")
    show = {"pending": "hidden", "approved": "shared"}.get(show, show)
    if show not in ("hidden", "shared", "all"):
        show = "all"
    selected = [item for item in active if show == "all"
                or (show == "shared") == photo_is_shared(item)]

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
        shared=sum(photo_is_shared(item) for item in active),
        is_shared=photo_is_shared,
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
    if action not in ("show", "hide", "delete"):
        abort(404)
    try:
        review_photo(photo_id, action, actor=current_admin_username() or "host")
    except (FileNotFoundError, ValueError):
        abort(404)
    messages = {"show": "Photo shown in the guest gallery.",
                "hide": "Photo hidden from the guest gallery.",
                "delete": "Photo permanently removed."}
    flash(messages[action], "success")
    return redirect(url_for("photos.admin_photos"))
