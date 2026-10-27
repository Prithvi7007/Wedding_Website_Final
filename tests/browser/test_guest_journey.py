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
    finally:
        page.close()


def test_mobile_navigation_and_qa_are_readable(browser, wedding_url):
    page = guest_page(browser, wedding_url, width=390, height=844)
    try:
        page.get_by_role("link", name="Q&A", exact=True).click()
        expect(page.get_by_role("heading", name="Questions & Answers")).to_be_visible()
        page.get_by_text("Can I bring a guest?").click()
        expect(page.get_by_text("Your RSVP form shows the exact number")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth") <= 392
        assert page.locator(".qa-item summary strong").first.evaluate(
            "el => getComputedStyle(el).color"
        ) != "rgb(0, 0, 0)"
    finally:
        page.close()


def test_rsvp_keyboard_escape_and_focus_return(browser, wedding_url):
    page = guest_page(browser, wedding_url)
    try:
        page.get_by_role("link", name="Schedule", exact=True).click()
        trigger = page.get_by_role("button", name="RSVP Now")
        trigger.focus()
        page.keyboard.press("Enter")
        expect(page.locator("#rsvp-overlay-haldi")).to_have_attribute("aria-hidden", "false")
        page.keyboard.press("Escape")
        expect(page.locator("#rsvp-overlay-haldi")).to_have_attribute("aria-hidden", "true")
        expect(trigger).to_be_focused()
    finally:
        page.close()
