"""Real Chromium guest journey tests; only local, disposable SQLite data.

Run in CI with:
    python -m pip install playwright==1.56.0
    python -m playwright install --with-deps chromium
    python -m pytest -q tests/browser

No real invitation links, production databases or Wedding admin credentials.
"""
from datetime import date, time
import re
import sqlite3
import threading

import pytest
from sqlalchemy import event as sqlalchemy_event
from werkzeug.serving import make_server

playwright = pytest.importorskip("playwright.sync_api")
expect = playwright.expect
sync_playwright = playwright.sync_playwright

from app import create_app
from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission


@pytest.fixture()
def wedding_url():
    app = create_app("testing")
    httpd = make_server("127.0.0.1", 0, app, threaded=False)
    started = threading.Event()
    errors = []

    def serve():
        with app.app_context():
            def register_sqlite(dbapi_connection, _record):
                if isinstance(dbapi_connection, sqlite3.Connection):
                    dbapi_connection.create_function(
                        "btrim", 1, lambda x: x.strip() if x is not None else None
                    )

            sqlalchemy_event.listen(db.engine, "connect", register_sqlite)
            try:
                db.create_all()
                guest = Invitation(
                    first_name="Browser",
                    display_name="Browser Guest",
                    invite_token="browser-fixture-token",
                    is_active=True,
                )
                event = Event(
                    event_id="haldi", title="Haldi",
                    event_date=date(2026, 11, 19),
                    start_time=time(12, 0), end_time=time(15, 0),
                    timezone="America/New_York",
                    location="Tampa, Florida", venue_name="Tampa",
                    display_order=1,
                )
                db.session.add_all((guest, event))
                db.session.flush()
                db.session.add(InvitationEventPermission(
                    invitation_id=guest.invitation_id,
                    event_id=event.event_id,
                    max_guests=2,
                ))
                db.session.commit()
                started.set()
                httpd.serve_forever()
            except Exception as exc:
                errors.append(exc)
                started.set()
            finally:
                db.session.remove()
                db.drop_all()
                sqlalchemy_event.remove(db.engine, "connect", register_sqlite)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert started.wait(timeout=15), "Local browser test server did not start"
    if errors:
        httpd.server_close()
        raise errors[0]
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    thread.join(timeout=15)
    httpd.server_close()
    assert not thread.is_alive()
    assert not errors


@pytest.fixture()
def browser():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        yield browser
        browser.close()


def guest_page(browser, wedding_url, *, width=1440, height=900):
    page = browser.new_page(
        viewport={"width": width, "height": height},
        reduced_motion="reduce",
    )
    page.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"),
               lambda route: route.abort())
    page.goto(f"{wedding_url}/invite/browser-fixture-token")
    expect(page.get_by_role("button", name="Open your private wedding invitation")).to_be_visible()
    page.get_by_role("button", name="Open your private wedding invitation").click()
    expect(page).to_have_url(re.compile(r"/dashboard"))
    expect(page.get_by_role("navigation", name="Wedding portal navigation")).to_be_visible()
    return page


def test_desktop_invitation_rsvp_save_and_persistence(browser, wedding_url):
    page = guest_page(browser, wedding_url)
    try:
        page.get_by_role("link", name="Schedule", exact=True).click()
        expect(page.get_by_role("heading", name="Wedding Schedule")).to_be_visible()
        page.get_by_role("button", name="RSVP Now").click()
        form = page.locator("#rsvp-form-haldi")
        expect(form).to_be_visible()
        form.locator('input[name="attending"][value="Yes"]').check(force=True)
        form.locator("textarea[name=notes]").fill("Vegetarian")
        form.locator("button.confirm-response-btn").click()
        expect(page.locator("#event-card-haldi [data-response-text]")).to_contain_text("Attending")
        page.reload()
        expect(page.locator("#event-card-haldi [data-response-text]")).to_contain_text("Attending")
        expect(page.get_by_role("button", name="Edit Response")).to_be_visible()
        page.get_by_role("link", name="Welcome", exact=True).click()
        expect(page.locator('[data-weekend-event-id="haldi"]')).to_contain_text("Attending")
        expect(page.locator(".weekend-cta")).to_contain_text("Explore your schedule")
    finally:
        page.close()


@pytest.mark.parametrize("width", [320, 390, 430])
def test_mobile_navigation_and_qa_are_readable(browser, wedding_url, width):
    page = guest_page(browser, wedding_url, width=width, height=844)
    try:
        page.get_by_role("link", name="Q&A", exact=True).click()
        expect(page.get_by_role("heading", name="Questions & Answers")).to_be_visible()
        page.get_by_text("Can I bring a guest?").click()
        expect(page.get_by_text("Your RSVP form shows the exact number")).to_be_visible()
        actual_width = page.evaluate("document.documentElement.scrollWidth")
        assert actual_width <= width + 2, (
            f"Q&A document overflow at {width}px viewport: "
            f"scrollWidth={actual_width}px"
        )
        assert page.locator(".qa-item summary strong").first.evaluate(
            "el => getComputedStyle(el).color"
        ) != "rgb(0, 0, 0)"
    finally:
        page.close()


@pytest.mark.parametrize("close_delay_ms", [0, 90])
def test_rsvp_keyboard_escape_and_focus_return(browser, wedding_url, close_delay_ms):
    page = guest_page(browser, wedding_url)
    try:
        page.get_by_role("link", name="Schedule", exact=True).click()
        trigger = page.get_by_role("button", name="RSVP Now")
        trigger.focus()
        page.keyboard.press("Enter")
        expect(page.locator("#rsvp-overlay-haldi")).to_have_attribute("aria-hidden", "false")
        if close_delay_ms:
            page.wait_for_timeout(close_delay_ms)
        # The dialog must take focus whenever it opens, not only on a timer.
        close_button = page.locator("#rsvp-overlay-haldi .overlay-close")
        expect(close_button).to_be_focused()
        if close_delay_ms:
            # Browser blur must not leave keyboard users stranded behind a modal.
            close_button.evaluate("button => button.blur()")
            expect(close_button).to_be_focused()
        page.keyboard.press("Escape")
        expect(page.locator("#rsvp-overlay-haldi")).to_have_attribute("aria-hidden", "true")
        # Detect delayed focus stealing from an already-closed overlay.
        page.wait_for_timeout(110)
        expect(trigger).to_be_focused()
    finally:
        page.close()

@pytest.mark.parametrize("width", [320, 390, 430])
def test_mobile_personal_weekend_preview_and_rsvp_link(browser, wedding_url, width):
    page = guest_page(browser, wedding_url, width=width, height=844)
    try:
        preview = page.locator('[data-weekend-event-id="haldi"]')
        expect(preview).to_contain_text("Awaiting your RSVP")
        expect(page.locator(".weekend-cta")).to_contain_text("Continue your RSVP")
        preview.scroll_into_view_if_needed()
        actual_width = page.evaluate("document.documentElement.scrollWidth")
        assert actual_width <= width + 2, (
            f"Welcome weekend overflow at {width}px viewport: "
            f"scrollWidth={actual_width}px"
        )
        page.locator(".weekend-cta").click()
        expect(page.get_by_role("heading", name="Wedding Schedule")).to_be_visible()
        expect(page.get_by_role("button", name="RSVP Now")).to_be_visible()
        expect(page.locator("#event-title-haldi")).to_be_focused()
    finally:
        page.close()


def test_welcome_event_link_targets_invited_event_after_navigation_and_refresh(browser, wedding_url):
    page = guest_page(browser, wedding_url)
    try:
        event_link = page.get_by_role("link", name="View Haldi in your schedule")
        expect(event_link).to_have_attribute("href", re.compile(r"tab=schedule.*event=haldi"))
        event_link.click()
        expect(page).to_have_url(re.compile(r"tab=schedule.*event=haldi"))
        expect(page.locator("#event-title-haldi")).to_be_focused()
        expect(page.locator("#event-card-haldi")).to_be_visible()

        # History and copied links preserve which event the guest selected.
        page.reload()
        expect(page.locator("#event-title-haldi")).to_be_focused()
        page.go_back()
        expect(page.locator(".weekend-event-link")).to_be_visible()
        page.go_forward()
        expect(page.locator("#event-title-haldi")).to_be_focused()

        # Uninvited or obsolete event IDs cannot target content outside
        # this guest's permitted schedule.
        page.goto(f"{wedding_url}/dashboard?tab=schedule&event=uninvited")
        expect(page.get_by_role("heading", name="Wedding Schedule")).to_be_visible()
        expect(page.locator('[data-schedule-event="uninvited"]')).to_have_count(0)
    finally:
        page.close()


@pytest.mark.parametrize("width", [320, 390, 430])
def test_wedding_weekend_calendar_download_on_mobile(browser, wedding_url, width):
    page = guest_page(browser, wedding_url, width=width, height=844)
    try:
        page.get_by_role("link", name="Schedule", exact=True).click()
        link = page.get_by_role(
            "link",
            name="Download all celebrations in your private invitation as a calendar file",
        )
        expect(link).to_be_visible()
        with page.expect_download() as download_info:
            link.click()
        download = download_info.value
        assert download.suggested_filename == "adlin-prithvi-weekend.ics"
        data = download.path().read_text(encoding="utf-8")
        assert "BEGIN:VEVENT" in data
        assert "SUMMARY:Haldi" in data
        # Check the new control directly. The tab navigation is an
        # intentionally horizontal scroller on narrow screens.
        bounds = link.evaluate("""element => {
            const rect = element.getBoundingClientRect();
            return {left: rect.left, right: rect.right};
        }""")
        assert bounds["left"] >= -2
        assert bounds["right"] <= width + 2
    finally:
        page.close()


@pytest.mark.parametrize("width", [320, 390, 430])
def test_schedule_layout_has_no_page_wide_horizontal_scroll(browser, wedding_url, width):
    page = guest_page(browser, wedding_url, width=width, height=844)
    try:
        page.get_by_role("link", name="Schedule", exact=True).click()
        expect(page.get_by_role("heading", name="Wedding Schedule")).to_be_visible()
        diagnostic = page.evaluate("""() => {
            const measure = () => document.documentElement.scrollWidth;
            const baseline = measure();
            const selectors = [
                '.dashboard-header', '.dashboard-tabs', '.dashboard-shell',
                '.schedule-panel', '.schedule-intro', '.schedule-journey',
                '.cinematic-event-list', '.cinematic-event-card',
                '.event-glass-panel', '.ambient-slideshow',
                '.rsvp-petal-container', '.rsvp-petal-canvas',
            ];
            const results = {};
            for (const selector of selectors) {
                const node = document.querySelector(selector);
                if (!node) continue;
                const before = node.style.display;
                node.style.display = 'none';
                results[selector] = measure();
                node.style.display = before;
            }
            return {baseline, results};
        }""")
        assert diagnostic["baseline"] <= width + 2, (
            f"Schedule page width {width}: {diagnostic}"
        )
    finally:
        page.close()
