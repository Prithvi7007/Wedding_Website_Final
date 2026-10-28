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
        # The schedule loads through an async tab fragment. Wait until the
        # navigation handler is ready and the newly inserted layout has
        # settled before measuring page-wide overflow. A visible heading can
        # appear one rendering frame before the outgoing panel is removed.
        expect(page.locator("html")).to_have_attribute(
            "data-fragment-navigation-ready", "true"
        )
        page.get_by_role("link", name="Schedule", exact=True).click()
        expect(page.get_by_role("heading", name="Wedding Schedule")).to_be_visible()
        page.wait_for_function("""() => {
            const panel = document.querySelector('[data-tab-panel="schedule"]');
            return panel && panel.isConnected &&
                document.documentElement.scrollWidth <= innerWidth + 2;
        }""", timeout=10000)
        actual_width = page.evaluate("document.documentElement.scrollWidth")
        assert actual_width <= width + 2, (
            f"Schedule should not scroll sideways at {width}px: "
            f"document width {actual_width}px"
        )
        tabs = page.locator(".dashboard-tabs")
        # Preserve deliberate, touch-scrollable top navigation.
        assert tabs.evaluate("node => getComputedStyle(node).overflowX") == "auto"
    finally:
        page.close()

@pytest.mark.parametrize("delayed_outcome", ["success", "error"])
def test_rapid_tab_switch_ignores_stale_response(browser, wedding_url, delayed_outcome):
    page = guest_page(browser, wedding_url, width=390, height=844)
    try:
        # Only exercise the enhanced navigation after the ES module has bound
        # its click listener; otherwise a fast CI runner may follow the href.
        expect(page.locator("html")).to_have_attribute(
            "data-fragment-navigation-ready", "true"
        )
        # Make the first fragment request finish *after* a later tab request.
        # The success case simulates a fetch that cannot be canceled by
        # AbortController; the failure case simulates a late network error.
        page.evaluate("""() => {
            const originalFetch = window.fetch.bind(window);
            window.__releaseTravel = null;
            window.__travelSettled = false;
            window.fetch = (url, options) => {
                if (!String(url).includes("/dashboard/tab/travel")) {
                    return originalFetch(url, options);
                }
                return new Promise((resolve, reject) => {
                    document.documentElement.dataset.travelIntercepted = "yes";
                    window.__releaseTravel = shouldFail => {
                        if (shouldFail) {
                            window.__travelSettled = true;
                                document.documentElement.dataset.travelSettled = "yes";
                            reject(new Error("simulated stale network failure"));
                            return;
                        }
                        originalFetch(url, {...options, signal: undefined}).then(
                            response => {
                                window.__travelSettled = true;
                                document.documentElement.dataset.travelSettled = "yes";
                                resolve(response);
                            },
                            error => {
                                window.__travelSettled = true;
                                document.documentElement.dataset.travelSettled = "yes";
                                reject(error);
                            },
                        );
                    };
                });
            };
        }""")

        page.get_by_role("link", name="Travel", exact=True).click()
        expect(page.locator("html")).to_have_attribute(
            "data-travel-intercepted", "yes"
        )
        page.get_by_role("link", name="Q&A", exact=True).click()

        expect(page.get_by_role("heading", name="Questions & Answers")).to_be_visible()
        expect(page.locator(".dashboard-tab[data-tab-name='qa']")).to_have_attribute(
            "aria-current", "page"
        )

        page.evaluate("(fail) => window.__releaseTravel(fail)", delayed_outcome == "error")
        expect(page.locator("html")).to_have_attribute("data-travel-settled", "yes")

        # The stale response/error must not overwrite the chosen tab or force
        # a full reload. History, loading state and accessibility stay synced.
        expect(page.get_by_role("heading", name="Questions & Answers")).to_be_visible()
        expect(page).to_have_url(re.compile(r"tab=qa"))
        expect(page.locator("body")).to_have_attribute("data-active-tab", "qa")
        expect(page.locator(".dashboard-tab[data-tab-name='qa']")).to_have_attribute(
            "aria-current", "page"
        )
        expect(page.locator("#tab-content")).not_to_have_attribute("aria-busy", "true")
        assert page.locator("#tab-content [data-tab-panel='travel']").count() == 0
    finally:
        page.close()

@pytest.mark.parametrize("width", [320, 390, 768, 1440, 1920])
def test_heritage_preview_preserves_original_invitation_identity_and_fullscreen_photos(
    browser, wedding_url, width,
):
    page = guest_page(
        browser, wedding_url,
        width=width, height=844 if width <= 430 else 900,
    )
    try:
        page.goto(f"{wedding_url}/dashboard/preview/guest-v2")
        expect(page.get_by_role("heading", name="Adlin & Prithvi")).to_be_visible()
        expect(page.get_by_role("heading", name="Browser Guest")).to_be_visible()
        expect(page.get_by_role("heading", name="The celebrations ahead.")).to_be_visible()
        expect(page.get_by_role("link", name="View your wedding weekend")).to_be_visible()
        expect(page.locator("[data-countdown-days]")).to_have_text(re.compile(r"[0-9]+"))
        assert "Parisienne" in page.locator(".heritage-signature").evaluate(
            "el => getComputedStyle(el).fontFamily"
        )

        # The original six curated photos, rather than a boxed split portrait.
        expect(page.locator("[data-slide-index]")).to_have_count(6)
        image = page.locator(".ambient-slide.is-active img")
        assert image.evaluate("el => el.complete && el.naturalWidth > 0")
        assert image.evaluate("el => getComputedStyle(el).objectFit") == "cover"
        expect(page.locator("html")).to_have_attribute(
            "data-heritage-gallery-ready", "true"
        )

        hero = page.locator(".heritage-hero").bounding_box()
        photo = page.locator(".ambient-slideshow").bounding_box()
        assert hero and photo
        viewport_h = 844 if width <= 430 else 900
        assert hero["width"] >= width - 2
        assert photo["width"] >= width - 2
        assert photo["height"] >= viewport_h - 2
        assert page.evaluate("document.documentElement.scrollWidth") <= width + 2

        # Photo navigation remains under guest control with reduced motion.
        page.get_by_role("button", name="Next photograph").click()
        expect(page.locator('[data-slide-index="1"]')).to_have_attribute(
            "aria-current", "true"
        )

        # Permissions and real event artwork, not a generic chapter card.
        page.get_by_role("link", name="View your wedding weekend").click()
        assert page.evaluate("location.hash") == "#celebrations"
        event = page.locator("#heritage-event-haldi")
        event.scroll_into_view_if_needed()
        expect(event.get_by_role("heading", name="Haldi")).to_be_visible()
        expect(event.get_by_text("Awaiting your RSVP")).to_be_visible()
        expect(event.get_by_text("12:00 PM")).to_be_visible()
        art = event.locator(".heritage-event-art img")
        assert art.evaluate("el => el.complete && el.naturalWidth > 0")
        assert art.evaluate("el => getComputedStyle(el).objectFit") == "cover"
        assert event.bounding_box()["width"] >= width - 2
        assert page.evaluate("document.documentElement.scrollWidth") <= width + 2

        assert page.locator("form").count() == 0
        expect(event.get_by_role("link", name="RSVP for this event")).to_have_attribute(
            "href", re.compile(r"tab=schedule.*event=haldi")
        )
    finally:
        page.close()


@pytest.mark.parametrize("width", [390, 1440])
def test_heritage_preview_glass_accessibility_and_live_site_isolation(
    browser, wedding_url, width,
):
    page = guest_page(
        browser, wedding_url,
        width=width, height=844 if width < 800 else 900,
    )
    try:
        page.goto(f"{wedding_url}/dashboard/preview/guest-v2")
        glass = page.locator(".heritage-event-glass")
        glass.scroll_into_view_if_needed()
        assert "blur(" in glass.evaluate(
            "el => getComputedStyle(el).backdropFilter"
        )

        toggle = page.locator("button[data-heritage-transparency]")
        expect(toggle).to_have_attribute("aria-pressed", "false")
        toggle.click()
        expect(toggle).to_have_attribute("aria-pressed", "true")
        expect(page.locator("body")).to_have_attribute(
            "data-heritage-transparency", "solid"
        )
        assert glass.evaluate(
            "el => getComputedStyle(el).backdropFilter"
        ) == "none"
        toggle.click()
        expect(toggle).to_have_attribute("aria-pressed", "false")
        expect(page.locator("body")).to_have_attribute(
            "data-heritage-transparency", "glass"
        )

        page.emulate_media(contrast="more")
        assert glass.evaluate("el => getComputedStyle(el).backdropFilter") == "none"
        expect(page.get_by_role("link", name="Original invitation", exact=True)).to_be_visible()
    finally:
        page.close()

@pytest.mark.parametrize("width", [320, 390, 768, 1440, 1920])
def test_original_heritage_glass_uses_screen_width_on_every_guest_tab(
    browser, wedding_url, width,
):
    page = guest_page(
        browser, wedding_url, width=width,
        height=844 if width <= 430 else 900,
    )
    try:
        for tab, heading in (
            ("welcome", "Browser Guest"),
            ("schedule", "Wedding Schedule"),
            ("travel", "Travel Guide"),
            ("registry", None),
            ("qa", "Questions & Answers"),
        ):
            page.goto(f"{wedding_url}/dashboard?tab={tab}")
            expect(page.locator('body[data-active-tab]')).to_have_attribute(
                "data-active-tab", tab
            )
            expect(page.locator(".dashboard-title")).to_be_visible()
            if heading:
                expect(page.get_by_role("heading", name=heading)).to_be_visible()

            viewport_width = page.evaluate("window.innerWidth")
            content_width = page.evaluate("document.documentElement.scrollWidth")
            if content_width > viewport_width + 2:
                offenders = page.evaluate("""() =>
                    [...document.querySelectorAll('body *')]
                        .map(el => ({
                            name: el.tagName.toLowerCase() + '.' +
                                String(el.className || '').slice(0, 80),
                            right: Math.round(el.getBoundingClientRect().right),
                            left: Math.round(el.getBoundingClientRect().left),
                        }))
                        .filter(el => el.right > innerWidth + 2 || el.left < -2)
                        .slice(0, 8)
                """)
                pytest.fail(
                    f"{tab} overflows at {viewport_width}px: "
                    f"document={content_width}; elements={offenders}"
                )
            assert page.locator(".dashboard-header").bounding_box()["width"] >= width - 2
            assert page.locator(".ambient-slideshow").bounding_box()["width"] >= width - 2
            assert page.locator(".dashboard-content").bounding_box()["width"] >= width - 2

            if tab == "welcome":
                size = page.locator(".welcome-copy h2").evaluate(
                    "el => parseFloat(getComputedStyle(el).fontSize)"
                )
                assert size <= (59 if width > 700 else 54), (
                    f"Guest name too large at {width}px: {size}px"
                )
                assert page.locator(".welcome-copy").evaluate(
                    "el => getComputedStyle(el, '::before').backgroundImage"
                ) != "none"
            elif tab == "schedule":
                card = page.locator("#event-card-haldi")
                glass = card.locator(".event-glass-panel")
                expect(glass).to_be_visible()
                card_box = card.bounding_box()
                panel_box = glass.bounding_box()
                assert card_box and panel_box
                assert panel_box["x"] >= card_box["x"] - 2
                assert panel_box["x"] + panel_box["width"] <= (
                    card_box["x"] + card_box["width"] + 2
                )
                assert panel_box["y"] >= card_box["y"] - 2
                assert panel_box["y"] + panel_box["height"] <= (
                    card_box["y"] + card_box["height"] + 2
                )
                assert "schedule-haldi-" in card.evaluate(
                    "el => getComputedStyle(el).backgroundImage"
                )
                assert "blur(" in glass.evaluate(
                    "el => getComputedStyle(el).backdropFilter"
                )
                if width > 1080:
                    assert panel_box["width"] < card_box["width"] * .5
                assert page.locator(".schedule-journey").evaluate(
                    "el => getComputedStyle(el).position"
                ) == "relative"
            elif tab == "travel":
                assert "blur(" in page.locator(".travel-story").first.evaluate(
                    "el => getComputedStyle(el).backdropFilter"
                )
            elif tab == "qa":
                assert "blur(" in page.locator(".qa-grid").evaluate(
                    "el => getComputedStyle(el).backdropFilter"
                )
    finally:
        page.close()


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_heritage_schedule_rsvp_calendar_and_width_remain_functional(
    browser, wedding_url, width,
):
    page = guest_page(
        browser, wedding_url, width=width,
        height=844 if width < 700 else 900,
    )
    try:
        page.goto(f"{wedding_url}/dashboard?tab=schedule")
        card = page.locator("#event-card-haldi")
        expect(card.get_by_role("heading", name="Haldi")).to_be_visible()
        expect(card.get_by_role("button", name="RSVP Now")).to_be_visible()

        card.get_by_role("button", name="+ Calendar").click()
        menu = card.locator("#calendar-menu-haldi")
        expect(menu).to_be_visible()
        expect(menu.get_by_role("link", name="Apple Calendar")).to_be_visible()

        card.get_by_role("button", name="RSVP Now").click()
        form = page.locator("#rsvp-form-haldi")
        expect(form).to_be_visible()
        form.locator('input[name="attending"][value="Yes"]').check(force=True)
        form.locator("button.confirm-response-btn").click()
        expect(card.locator("[data-response-text]")).to_contain_text("Attending")
        assert page.evaluate("document.documentElement.scrollWidth") <= width + 2
    finally:
        page.close()
