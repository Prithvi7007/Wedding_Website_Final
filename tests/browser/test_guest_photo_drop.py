"""Chromium smoke test for the stand-alone QR guest photo experience."""
from io import BytesIO
import re
import shutil
import subprocess
import threading

import pytest
from werkzeug.serving import make_server

playwright = pytest.importorskip("playwright.sync_api")
Image = pytest.importorskip("PIL.Image")
expect = playwright.expect
sync_playwright = playwright.sync_playwright

from app.photos.storage import save_photos
from werkzeug.datastructures import FileStorage


TOKEN = "browser-photo-token-very-long-and-private-0001"


@pytest.fixture()
def photo_site(tmp_path, app):
    root = tmp_path / "wedding-uploads"
    (root / "files").mkdir(parents=True)
    (root / "metadata").mkdir(parents=True)
    app.config.update(
        WTF_CSRF_ENABLED=True,
        WTF_CSRF_SSL_STRICT=True,
        SESSION_COOKIE_SECURE=True,
        WEDDING_PHOTO_ENABLED=True,
        WEDDING_PHOTO_GALLERY_ENABLED=True,
        WEDDING_PHOTO_BACKEND="local",
        WEDDING_PHOTO_STORAGE_DIR=str(root),
        WEDDING_PHOTO_SHARE_TOKEN=TOKEN,
    )
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("HTTPS photo regression requires OpenSSL (available in CI)")
    certificate, key = tmp_path / "certificate.pem", tmp_path / "key.pem"
    subprocess.run(
        [openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", str(key), "-out", str(certificate), "-days", "1",
         "-subj", "/CN=localhost"],
        check=True, capture_output=True,
    )
    server = make_server("127.0.0.1", 0, app, threaded=True,
                         ssl_context=(str(certificate), str(key)))
    url = f"https://127.0.0.1:{server.server_port}"
    app.config["PUBLIC_BASE_URL"] = url
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield url, root
    finally:
        server.shutdown()
        thread.join(timeout=12)
        server.server_close()
        assert not thread.is_alive()


@pytest.fixture()
def browser():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_qr_guest_can_upload_photo_from_phone_without_login(browser, photo_site, width):
    url, root = photo_site
    page = browser.new_page(
        viewport={"width": width, "height": 844},
        reduced_motion="reduce",
        ignore_https_errors=True,
    )
    external_headers = []

    def block_external_font(route):
        external_headers.append(route.request.all_headers())
        route.abort()

    page.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"),
               block_external_font)
    try:
        page.goto(f"{url}/photos/{TOKEN}")
        assert external_headers
        assert all("referer" not in headers for headers in external_headers)
        expect(page.get_by_role("heading", name=re.compile("Every little moment"))).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
        assert page.locator(".photo-drop-card").bounding_box()["width"] <= width

        sample = BytesIO()
        Image.new("RGB", (750, 600), (110, 78, 60)).save(sample, "JPEG")
        page.locator('input[name="photos"]').set_input_files({
            "name": "moments.jpg", "mimeType": "image/jpeg", "buffer": sample.getvalue(),
        })
        expect(page.get_by_role("status")).to_contain_text("1 photo selected")
        page.get_by_role("textbox", name=re.compile("Your name")).fill("Wedding Guest")
        page.get_by_role("combobox", name="Which moment?").select_option("Reception")
        page.get_by_role("checkbox", name=re.compile("I agree")).check()
        with page.expect_response(lambda response: response.request.method == "POST"
                                  and response.url == f"{url}/photos/{TOKEN}") as upload:
            page.get_by_role("button", name=re.compile("Share this moment")).click()
        assert upload.value.status == 201

        expect(page).to_have_url(re.compile(r"/thanks\?count=1$"), timeout=12000)
        expect(page.get_by_role("heading", name="We got your moments.")).to_be_visible()
        assert len(list((root / "files").glob("*.jpg"))) == 1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
        assert page.request.get(f"{url}/admin/photos", max_redirects=0).status == 302
        photo_id = next((root / "files").glob("*.jpg")).stem
        image_url = f"{url}/photos/{TOKEN}/gallery/{photo_id}.jpg"
        assert page.request.get(image_url).status == 200
        page.get_by_role("link", name=re.compile("Explore the guest gallery")).click()
        expect(page.get_by_role("link", name="View Reception wedding photograph")).to_be_visible()
        assert page.request.get(image_url).status == 200
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
    finally:
        page.close()


def test_host_can_hide_show_and_delete_over_https(browser, photo_site, app):
    url, root = photo_site
    sample = BytesIO()
    Image.new("RGB", (100, 80), (110, 78, 60)).save(sample, "JPEG")
    sample.seek(0)
    with app.app_context():
        save_photos([FileStorage(stream=sample, filename="memory.jpg")],
                    "HTTPS Guest", "Reception", gallery_consent=True)
    photo_id = next((root / "files").glob("*.jpg")).stem
    image_url = f"{url}/photos/{TOKEN}/gallery/{photo_id}.jpg"
    page = browser.new_page(ignore_https_errors=True)
    page.on("dialog", lambda dialog: dialog.accept())
    try:
        page.goto(f"{url}/admin/login")
        page.locator("#username").fill("prithvi")
        page.locator("#password").fill("test-admin-password-for-testing")
        page.get_by_role("button", name="Open Admin Portal").click()
        expect(page).to_have_url(re.compile(r"/admin/?$"))
        page.goto(f"{url}/admin/photos")
        assert page.request.get(image_url).status == 200
        for action, label in (("hide", "Hide"), ("show", "Show"),
                              ("delete", "Permanently delete photo")):
            with page.expect_response(lambda response, action=action:
                                      response.request.method == "POST"
                                      and response.url.endswith(f"/{photo_id}/{action}")) as review:
                page.get_by_role("button", name=label, exact=True).click()
            assert review.value.status == 302
            expect(page.get_by_role("heading", name="Photo Collection")).to_be_visible()
            assert page.request.get(image_url).status == (200 if action == "show" else 404)
    finally:
        page.close()


@pytest.mark.parametrize("format,extension,mime", [
    ("PNG", "png", "image/png"), ("WEBP", "webp", "image/webp"),
    ("HEIF", "heic", "image/heic"), ("TIFF", "tiff", "application/octet-stream"),
])
def test_non_jpg_phone_uploads_appear_immediately(browser, photo_site, format, extension, mime):
    url, root = photo_site
    sample = BytesIO()
    image = Image.new("RGB", (160, 120), (110, 78, 60))
    if format == "HEIF":
        pytest.importorskip("pillow_heif").from_pillow(image).save(sample)
    else:
        image.save(sample, format)
    page = browser.new_page(ignore_https_errors=True, viewport={"width": 390, "height": 844})
    page.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"), lambda route: route.abort())
    try:
        page.goto(f"{url}/photos/{TOKEN}")
        page.locator('input[name="photos"]').set_input_files({
            "name": "camera." + extension, "mimeType": mime, "buffer": sample.getvalue(),
        })
        page.get_by_role("checkbox", name=re.compile("I agree")).check()
        with page.expect_response(lambda response: response.request.method == "POST"
                                  and response.url == f"{url}/photos/{TOKEN}", timeout=12000) as upload:
            page.get_by_role("button", name=re.compile("Share this moment")).click()
        assert upload.value.status == 201
        if format in {"HEIF", "TIFF"}:
            # Chromium cannot decode these inputs: ensure the original reached
            # server normalization rather than silently testing canvas JPEGs.
            assert (f'filename="camera.{extension}"'.encode()
                    in upload.value.request.post_data_buffer)
        expect(page.get_by_role("heading", name="We got your moments.")).to_be_visible()
        photo_id = next((root / "files").glob("*.jpg")).stem
        assert page.request.get(f"{url}/photos/{TOKEN}/gallery/{photo_id}.jpg").status == 200
    finally:
        page.close()


def test_phone_can_share_a_mixed_batch_above_two_mib(browser, photo_site):
    import random
    url, root = photo_site
    large = BytesIO()
    Image.frombytes("RGB", (1024, 1024), random.Random(17).randbytes(1024 * 1024 * 3)).save(large, "TIFF")
    assert len(large.getvalue()) > 2 * 1024 * 1024
    small = Image.new("RGB", (160, 120), (110, 78, 60))
    heic, jpg = BytesIO(), BytesIO()
    pytest.importorskip("pillow_heif").from_pillow(small).save(heic)
    small.save(jpg, "JPEG")
    page = browser.new_page(ignore_https_errors=True, viewport={"width": 390, "height": 844},
                            is_mobile=True, has_touch=True)
    page.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"), lambda route: route.abort())
    try:
        page.goto(f"{url}/photos/{TOKEN}")
        page.locator('input[name="photos"]').set_input_files([
            {"name": "large.tiff", "mimeType": "image/tiff", "buffer": large.getvalue()},
            {"name": "phone.heic", "mimeType": "image/heic", "buffer": heic.getvalue()},
            {"name": "memory.jpg", "mimeType": "image/jpeg", "buffer": jpg.getvalue()},
        ])
        expect(page.get_by_role("status")).to_contain_text("3 photos selected")
        # Exercise the mobile preview layout during scrolling before submission.
        page.locator(".photo-drop-preview").scroll_into_view_if_needed()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
        page.get_by_role("checkbox", name=re.compile("I agree")).check()
        with page.expect_response(lambda response: response.request.method == "POST"
                                  and response.url == f"{url}/photos/{TOKEN}", timeout=15000) as upload:
            page.get_by_role("button", name=re.compile("Share these moments")).click()
        assert upload.value.status == 201
        expect(page).to_have_url(re.compile(r"/thanks\?count=3$"))
        expect(page.get_by_role("heading", name="We got your moments.")).to_be_visible()
        assert len(list((root / "files").glob("*.jpg"))) == 3
        page.get_by_role("link", name=re.compile("Explore the guest gallery")).click()
        expect(page.locator(".photo-gallery-photo")).to_have_count(3)
    finally:
        page.close()
