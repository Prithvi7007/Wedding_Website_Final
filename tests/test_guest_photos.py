"""No-login QR photo sharing with immediate visibility and host controls.

All uploads run against an isolated temporary directory; never production.
"""
from io import BytesIO
import json
import re

import pytest

Image = pytest.importorskip("PIL.Image", reason="CI installs the image-processing requirements")

from app.photos.storage import MAX_IMAGE_BYTES


SHARE_TOKEN = "qr-photo-test-token-that-is-unguessable-001"
SHARE_PATH = f"/photos/{SHARE_TOKEN}"


@pytest.fixture()
def photo_inbox(app, tmp_path):
    root = tmp_path / "wedding-photo-inbox"
    (root / "files").mkdir(parents=True)
    (root / "metadata").mkdir(parents=True)
    app.config.update(
        WEDDING_PHOTO_ENABLED=True,
        WEDDING_PHOTO_GALLERY_ENABLED=True,
        WEDDING_PHOTO_BACKEND="local",
        WEDDING_PHOTO_STORAGE_DIR=str(root),
        WEDDING_PHOTO_SHARE_TOKEN=SHARE_TOKEN,
        PUBLIC_BASE_URL="http://localhost",
    )
    return root


def sample_jpg(*, with_exif=False):
    content = BytesIO()
    image = Image.new("RGB", (420, 260), color=(150, 104, 66))
    if with_exif:
        exif = Image.Exif()
        exif[270] = "LOCATION DATA SHOULD NEVER LEAVE THE PRIVATE DEVICE"
        image.save(content, format="JPEG", exif=exif)
    else:
        image.save(content, format="JPEG")
    content.seek(0)
    return content


def photo_form(image=None, **fields):
    return {
        "guest_name": fields.get("guest_name", "A dear guest"),
        "gallery_consent": "yes",
        "moment": fields.get("moment", "Haldi"),
        "photos": (image or sample_jpg(), "memory.jpg"),
    }


def login_host(client, username="prithvi", password="test-admin-password-for-testing"):
    response = client.post("/admin/login", data={"username": username, "password": password})
    assert response.status_code == 302


def test_default_closed_and_no_admin_setup_leak(client):
    assert client.get(SHARE_PATH).status_code == 404
    assert client.post(SHARE_PATH, data=photo_form()).status_code == 404
    assert client.get(SHARE_PATH + "/gallery").status_code == 404
    assert client.get("/admin/photos").status_code == 302
    login_host(client)
    admin = client.get("/admin/photos")
    assert admin.status_code == 200
    assert b"Not active yet" in admin.data
    assert SHARE_TOKEN.encode() not in admin.data
    assert client.get("/admin/photos/qr.svg").status_code == 404


def test_private_qr_and_guest_upload_page(client, photo_inbox):
    assert client.get("/photos/wrong-token-that-looks-long-enough").status_code == 404
    result = client.get(SHARE_PATH)
    assert result.status_code == 200
    assert b"Every little moment" in result.data
    assert b'name="csrf_token"' in result.data
    assert b'accept="image/*,.jpg,.jpeg,.png,.webp,.heic,.heif,.avif,.gif,.bmp,.tif,.tiff"' in result.data
    assert b"Guest Photos" not in result.data
    assert result.headers["X-Robots-Tag"].startswith("noindex")
    assert result.headers["Cache-Control"].startswith("private, no-store")
    assert "img-src 'self' data: blob:" in result.headers["Content-Security-Policy"]
    assert "img-src 'self' data: blob:" not in client.get("/").headers["Content-Security-Policy"]
    assert client.get("/photos/wrong-token-that-looks-long-enough/gallery").status_code == 404


def test_upload_strips_exif_shares_immediately_and_preserves_host_controls(client, photo_inbox):
    response = client.post(
        SHARE_PATH, data=photo_form(sample_jpg(with_exif=True)),
        content_type="multipart/form-data",
    )
    assert response.status_code == 303
    assert response.headers["Location"].startswith(SHARE_PATH + "/thanks")
    thanks = client.get(response.headers["Location"])
    assert thanks.status_code == 200
    assert b"We got your moments" in thanks.data

    images = list((photo_inbox / "files").glob("*.jpg"))
    assert len(images) == 1
    record_id = images[0].stem
    assert re.fullmatch(r"[a-f0-9]{32}", record_id)
    with Image.open(images[0]) as cleaned:
        assert cleaned.format == "JPEG"
        assert cleaned.getexif() == {}
        assert cleaned.width == 420 and cleaned.height == 260

    private_path = f"/admin/photos/{record_id}/image"
    guest_image_path = f"{SHARE_PATH}/gallery/{record_id}.jpg"
    gallery = client.get(SHARE_PATH + "/gallery")
    assert gallery.status_code == 200
    assert record_id.encode() in gallery.data
    assert b"A dear guest" not in gallery.data  # Names remain host-only.
    shared_image = client.get(guest_image_path)
    assert shared_image.status_code == 200
    assert shared_image.mimetype == "image/jpeg"
    assert shared_image.headers["Cache-Control"].startswith("private, no-store")
    assert client.get(private_path).status_code == 302
    assert client.get(f"/photos/{SHARE_TOKEN}/{record_id}").status_code == 404

    login_host(client)
    page = client.get("/admin/photos")
    assert page.status_code == 200
    assert b"A dear guest" in page.data
    assert b"Haldi" in page.data
    assert SHARE_TOKEN.encode() in page.data
    assert b"Shared" in page.data

    image_result = client.get(private_path)
    assert image_result.status_code == 200
    assert image_result.mimetype == "image/jpeg"
    assert image_result.headers["Cache-Control"].startswith("private, no-store")
    download = client.get(private_path + "?download=1")
    assert download.status_code == 200
    assert download.headers["Content-Disposition"].startswith("attachment;")

    code = client.get("/admin/photos/qr.svg")
    assert code.status_code == 200
    assert code.mimetype == "image/svg+xml"
    assert b"<svg" in code.data
    assert code.headers["X-Robots-Tag"].startswith("noindex")

    assert client.post(f"/admin/photos/{record_id}/hide").status_code == 302
    assert client.get(guest_image_path).status_code == 404
    assert record_id.encode() not in client.get(SHARE_PATH + "/gallery").data
    assert client.post(f"/admin/photos/{record_id}/show").status_code == 302
    assert client.get(guest_image_path).status_code == 200
    removed = client.post(f"/admin/photos/{record_id}/delete")
    assert removed.status_code == 302
    assert not images[0].exists()
    assert client.get(private_path).status_code == 404
    assert client.get(guest_image_path).status_code == 404
    assert record_id.encode() not in client.get(SHARE_PATH + "/gallery").data
    assert client.post(f"/admin/photos/{record_id}/approve").status_code == 404


def test_upload_accepts_batch_and_escapes_untrusted_name(client, photo_inbox):
    payload = {
        "guest_name": "<script>alert('hello')</script>",
        "gallery_consent": "yes",
        "moment": "Reception",
        "photos": [(sample_jpg(), "one.jpg"), (sample_jpg(), "two.jpg")],
    }
    response = client.post(SHARE_PATH, data=payload,
                           content_type="multipart/form-data",
                           headers={"Accept": "application/json"})
    assert response.status_code == 201
    assert response.json == {"success": True, "count": 2}

    login_host(client)
    page = client.get("/admin/photos")
    assert page.status_code == 200
    assert b"&lt;script&gt;" in page.data
    assert b"<script>alert('hello')</script>" not in page.data


def test_invalid_mime_oversized_and_more_than_six_are_atomic(client, photo_inbox):
    bad = client.post(
        SHARE_PATH,
        data=photo_form(BytesIO(b'<svg onload="alert(1)"/>')),
        content_type="multipart/form-data",
    )
    assert bad.status_code == 400
    assert b"could not be read" in bad.data

    big = client.post(
        SHARE_PATH,
        data=photo_form(BytesIO(b"X" * (MAX_IMAGE_BYTES + 1))),
        content_type="multipart/form-data",
    )
    assert big.status_code == 400
    assert b"too large" in big.data

    seven = client.post(
        SHARE_PATH,
        data={
            "moment": "Wedding weekend",
            "gallery_consent": "yes",
            "photos": [(sample_jpg(), f"photo-{n}.jpg") for n in range(7)],
        },
        content_type="multipart/form-data",
    )
    assert seven.status_code == 400
    assert b"between 1 and 6" in seven.data
    assert list((photo_inbox / "files").glob("*")) == []
    assert list((photo_inbox / "metadata").glob("*.json")) == []


def test_production_like_guards_reject_unready_storage_and_invalid_url(client, app, photo_inbox):
    app.config["PUBLIC_BASE_URL"] = "https://phishing.example/fake/path"
    assert client.get(SHARE_PATH).status_code == 404
    app.config["PUBLIC_BASE_URL"] = "http://localhost"
    app.config["WEDDING_PHOTO_STORAGE_DIR"] = str(photo_inbox / "missing")
    assert client.get(SHARE_PATH).status_code == 404
    app.config["WEDDING_PHOTO_STORAGE_DIR"] = str(photo_inbox)
    app.config["WEDDING_PHOTO_SHARE_TOKEN"] = "short"
    assert client.get(SHARE_PATH).status_code == 404


def test_viewer_cannot_review_or_download_guest_photos(client, photo_inbox):
    result = client.post(SHARE_PATH, data=photo_form(), content_type="multipart/form-data")
    assert result.status_code == 303
    photo_id = next((photo_inbox / "files").glob("*.jpg")).stem
    login_host(client, username="adlin_fam",
               password="test-adlin-family-password")
    assert client.get("/admin/photos").status_code == 302
    assert client.get("/admin/photos/qr.svg").status_code == 302
    assert client.get(f"/admin/photos/{photo_id}/image").status_code == 302
    assert client.post(f"/admin/photos/{photo_id}/delete").status_code == 302
    assert next((photo_inbox / "files").glob("*.jpg")).exists()


def test_honeypot_and_missing_upload_dont_store_content(client, photo_inbox):
    assert client.post(SHARE_PATH, data={"website": "spam",
        "photos": (sample_jpg(), "test.jpg")}, content_type="multipart/form-data").status_code == 400
    response = client.post(SHARE_PATH, data={"moment": "Wedding weekend", "gallery_consent": "yes"},
                           content_type="multipart/form-data")
    assert response.status_code == 400
    assert b"Choose between 1 and 6" in response.data
    assert list((photo_inbox / "files").glob("*")) == []


def test_upload_response_rejects_invalid_moment(client, photo_inbox):
    response = client.post(SHARE_PATH,
        data=photo_form(moment="a different event"),
        content_type="multipart/form-data",
        headers={"Accept": "application/json"})
    assert response.status_code == 400
    assert response.json["success"] is False
    assert "valid celebration" in response.json["message"]

def test_gallery_requires_explicit_upload_consent(client, photo_inbox):
    form = photo_form()
    del form["gallery_consent"]
    response = client.post(
        SHARE_PATH, data=form, content_type="multipart/form-data",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json["success"] is False
    assert "guest gallery" in response.json["message"]
    assert not list((photo_inbox / "files").glob("*.jpg"))

def test_guest_gallery_has_independent_feature_switch(client, app, photo_inbox):
    assert client.get(SHARE_PATH).status_code == 200
    app.config["WEDDING_PHOTO_GALLERY_ENABLED"] = False
    assert client.get(SHARE_PATH + "/gallery").status_code == 404
    assert client.get(SHARE_PATH).status_code == 200


def test_legacy_unconsented_photo_cannot_be_shown(client, photo_inbox):
    response = client.post(SHARE_PATH, data=photo_form(),
                           content_type="multipart/form-data")
    assert response.status_code == 303
    photo_id = next((photo_inbox / "files").glob("*.jpg")).stem
    meta = photo_inbox / "metadata" / f"{photo_id}.json"
    record = json.loads(meta.read_text(encoding="utf-8"))
    record.pop("gallery_consent", None)
    meta.write_text(json.dumps(record), encoding="utf-8")
    login_host(client)
    assert client.post(f"/admin/photos/{photo_id}/show").status_code == 404
    assert photo_id.encode() not in client.get(SHARE_PATH + "/gallery").data
    assert client.get(f"{SHARE_PATH}/gallery/{photo_id}.jpg").status_code == 404


def test_gallery_remains_accessible_after_uploads_close(client, app, photo_inbox):
    response = client.post(SHARE_PATH, data=photo_form(),
                           content_type="multipart/form-data")
    assert response.status_code == 303
    photo_id = next((photo_inbox / "files").glob("*.jpg")).stem
    login_host(client)
    app.config["WEDDING_PHOTO_ENABLED"] = False
    assert client.get(SHARE_PATH).status_code == 404
    assert client.get(SHARE_PATH + "/gallery").status_code == 200
    assert client.get(f"{SHARE_PATH}/gallery/{photo_id}.jpg").status_code == 200
    admin = client.get("/admin/photos")
    assert admin.status_code == 200
    assert b"Preview guest gallery" in admin.data
    assert b"admin/photos/qr.svg" not in admin.data


def test_read_only_gallery_does_not_reveal_qr_link_in_referrers(client, photo_inbox):
    gallery = client.get(SHARE_PATH + "/gallery")
    assert gallery.headers["Referrer-Policy"] == "no-referrer"


@pytest.mark.parametrize("invalid", ["missing-token", "bad-token", "missing-referrer", "foreign-referrer"])
def test_https_photo_upload_keeps_csrf_protection(client, app, photo_inbox, invalid):
    base = "https://localhost"
    app.config.update(WTF_CSRF_ENABLED=True, WTF_CSRF_SSL_STRICT=True,
                      PUBLIC_BASE_URL=base, SESSION_COOKIE_SECURE=True)
    page = client.get(SHARE_PATH, base_url=base)
    csrf = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
    payload = photo_form()
    payload["csrf_token"] = csrf
    headers = {"Accept": "application/json", "Referer": base + SHARE_PATH}
    if invalid == "missing-token":
        del payload["csrf_token"]
    elif invalid == "bad-token":
        payload["csrf_token"] = "invalid"
    elif invalid == "missing-referrer":
        del headers["Referer"]
    else:
        headers["Referer"] = "https://other.example/"
    response = client.post(SHARE_PATH, base_url=base, data=payload,
                           content_type="multipart/form-data", headers=headers)
    assert response.status_code == 400
    assert response.json["success"] is False
    assert not list((photo_inbox / "files").glob("*.jpg"))


def test_consented_upload_is_instantly_visible_without_host_actions(client, photo_inbox):
    result = client.post(SHARE_PATH, data=photo_form(), content_type="multipart/form-data")
    assert result.status_code == 303
    photo_id = next((photo_inbox / "files").glob("*.jpg")).stem
    assert photo_id.encode() in client.get(SHARE_PATH + "/gallery").data
    assert client.get(f"{SHARE_PATH}/gallery/{photo_id}.jpg").status_code == 200


@pytest.mark.parametrize("format,extension", [
    ("JPEG", "jpeg"), ("PNG", "png"), ("WEBP", "webp"), ("HEIF", "heic"),
    ("AVIF", "avif"), ("GIF", "gif"), ("BMP", "bmp"), ("TIFF", "tiff"),
])
def test_real_photo_input_formats_are_normalized_and_shared(client, photo_inbox, format, extension):
    source = BytesIO()
    image = Image.new("RGB", (120, 80), (110, 78, 60))
    if format == "HEIF":
        heif = pytest.importorskip("pillow_heif")
        heif.from_pillow(image).save(source)
    else:
        image.save(source, format)
    source.seek(0)
    form = photo_form()
    form["photos"] = (source, "camera." + extension, "application/octet-stream")
    response = client.post(SHARE_PATH, data=form, content_type="multipart/form-data",
                           headers={"Accept": "application/json"})
    assert response.status_code == 201
    stored = next((photo_inbox / "files").glob("*.jpg"))
    with Image.open(stored) as normalized:
        assert normalized.format == "JPEG"
        assert normalized.getexif() == {}
        assert normalized.size == (120, 80)
    assert client.get(f"{SHARE_PATH}/gallery/{stored.stem}.jpg").status_code == 200


def test_host_can_hide_and_restore_a_shared_photo_in_one_step(client, photo_inbox):
    assert client.post(SHARE_PATH, data=photo_form(), content_type="multipart/form-data").status_code == 303
    photo_id = next((photo_inbox / "files").glob("*.jpg")).stem
    image_url = f"{SHARE_PATH}/gallery/{photo_id}.jpg"
    login_host(client)
    assert client.post(f"/admin/photos/{photo_id}/hide").status_code == 302
    assert client.get(image_url).status_code == 404
    assert client.post(f"/admin/photos/{photo_id}/show").status_code == 302
    assert client.get(image_url).status_code == 200
    page = client.get("/admin/photos")
    assert b">Approve</button>" not in page.data
    assert b">Publish</button>" not in page.data


def test_legacy_consented_hidden_photo_stays_hidden_until_host_shows_it(client, photo_inbox):
    assert client.post(SHARE_PATH, data=photo_form(), content_type="multipart/form-data").status_code == 303
    meta = next((photo_inbox / "metadata").glob("*.json"))
    record = json.loads(meta.read_text())
    record["status"] = "pending"
    record.pop("published_at")
    meta.write_text(json.dumps(record))
    image_url = f"{SHARE_PATH}/gallery/{meta.stem}.jpg"
    assert client.get(image_url).status_code == 404
    assert meta.stem.encode() not in client.get(SHARE_PATH + "/gallery").data
    assert client.post(SHARE_PATH, data=photo_form(), content_type="multipart/form-data").status_code == 303
    assert client.get(image_url).status_code == 404
    login_host(client)
    assert client.post(f"/admin/photos/{meta.stem}/show").status_code == 302
    assert client.get(image_url).status_code == 200


def test_mixed_valid_and_invalid_photos_do_not_share_a_partial_batch(client, photo_inbox):
    response = client.post(SHARE_PATH, data={
        "gallery_consent": "yes", "moment": "Reception",
        "photos": [(sample_jpg(), "valid.jpg"), (BytesIO(b"not a photo"), "bad.heic")],
    }, content_type="multipart/form-data", headers={"Accept": "application/json"})
    assert response.status_code == 400
    assert not list((photo_inbox / "files").glob("*.jpg"))
    assert not list((photo_inbox / "metadata").glob("*.json"))
