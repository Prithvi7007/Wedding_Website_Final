"""Chromium smoke test for the stand-alone QR guest photo experience."""
from io import BytesIO
import re
import threading

import pytest
from werkzeug.serving import make_server

playwright = pytest.importorskip("playwright.sync_api")
Image = pytest.importorskip("PIL.Image")
expect = playwright.expect
sync_playwright = playwright.sync_playwright

from app import create_app


TOKEN = "browser-photo-token-very-long-and-private-0001"


@pytest.fixture()
def photo_site(tmp_path):
    root = tmp_path / "wedding-uploads"
    (root / "files").mkdir(parents=True)
    (root / "metadata").mkdir(parents=True)
    app = create_app("testing")
    app.config.update(
        WEDDING_PHOTO_ENABLED=True,
        WEDDING_PHOTO_STORAGE_DIR=str(root),
        WEDDING_PHOTO_SHARE_TOKEN=TOKEN,
    )
    server = make_server("127.0.0.1", 0, app, threaded=True)
    url = f"http://127.0.0.1:{server.server_port}"
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
    )
    page.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"),
               lambda route: route.abort())
    try:
        page.goto(f"{url}/photos/{TOKEN}")
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
        page.get_by_role("button", name=re.compile("Share this moment")).click()

        expect(page).to_have_url(re.compile(r"/thanks\?count=1$"), timeout=12000)
        expect(page.get_by_role("heading", name="We got your moments.")).to_be_visible()
        assert len(list((root / "files").glob("*.jpg"))) == 1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
        assert page.request.get(f"{url}/admin/photos").status == 302
    finally:
        page.close()
