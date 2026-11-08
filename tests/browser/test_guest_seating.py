"""Actual HTTPS host and guest seating workflows with isolated records."""
from datetime import date, time
import re

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect
from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission, RSVP, SeatingAssignment, SeatingTable
from test_guest_photo_drop import browser, photo_site, TOKEN


@pytest.fixture()
def family_site(photo_site, app):
    url, root = photo_site
    with app.app_context():
        event = Event(event_id="reception", title="Wedding Reception", event_date=date(2026, 11, 21),
                      start_time=time(18), end_time=time(22), location="Tampa")
        family = Invitation(first_name="Alex", last_name="Brown", partner_name="Jordan Brown",
                            display_name="Alex & Jordan Brown Family", invite_token="private-browser-invite",
                            email="never-public@example.test", phone="never-public-phone", is_active=True)
        db.session.add_all([event, family]); db.session.flush()
        db.session.add(InvitationEventPermission(invitation_id=family.invitation_id, event_id="reception", max_guests=4))
        db.session.add(RSVP(invitation_id=family.invitation_id, event_id="reception", attending="Yes", guest_count=3))
        db.session.commit()
        family_id = family.invitation_id
    return url, family_id


def page_for(browser, width=390):
    page = browser.new_page(ignore_https_errors=True, viewport={"width": width, "height": 900})
    page.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"), lambda route: route.abort())
    return page


@pytest.mark.parametrize("width", [390, 1440])
def test_host_assigns_a_family_and_guest_finds_it_immediately(browser, family_site, width, tmp_path):
    url, family_id = family_site
    host, guest = page_for(browser, width), page_for(browser, width)
    host.on("dialog", lambda dialog: dialog.accept())
    try:
        host.goto(url + "/admin/login")
        host.locator("#username").fill("prithvi")
        host.locator("#password").fill("test-admin-password-for-testing")
        host.get_by_role("button", name="Open Admin Portal").click()
        expect(host).to_have_url(re.compile(r"/admin/?$"))
        host.get_by_role("link", name="Seating", exact=True).click()
        create = host.locator(".seating-create")
        create.get_by_label("Table name or number").fill("Table 7")
        create.get_by_label(re.compile("Capacity")).fill("2")
        create.get_by_role("button", name="Add table").click()
        expect(host.locator(".seating-table-card")).to_contain_text("Table 7")
        host.get_by_role("checkbox", name=re.compile("Alex & Jordan Brown Family")).check()
        host.get_by_label("Table for selected families").select_option(label="Table 7")
        host.get_by_role("button", name="Apply assignment").click()
        expect(host.locator(".seating-warning")).to_contain_text("Above the capacity")
        assert host.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
        host.screenshot(path=str(tmp_path / f"host-{width}.png"), full_page=True)

        guest.goto(f"{url}/photos/{TOKEN}/welcome")
        guest.screenshot(path=str(tmp_path / f"welcome-{width}.png"), full_page=True)
        guest.locator(".experience-actions").get_by_role("link", name=re.compile("Find your table")).click()
        guest.get_by_role("searchbox", name="Your name or family name").fill("jordan")
        guest.get_by_role("button", name="Find my table").click()
        expect(guest.locator(".seating-result")).to_contain_text("Table 7")
        expect(guest.locator(".seating-result")).to_contain_text("Alex & Jordan Brown Family")
        assert "never-public" not in guest.content()
        guest.screenshot(path=str(tmp_path / f"assigned-{width}.png"), full_page=True)

        card = host.locator(".seating-table-card")
        card.get_by_text("Edit table", exact=True).click()
        card.get_by_label("Table name", exact=True).fill("Garden")
        card.get_by_role("button", name="Save table").click()
        guest.reload()
        expect(guest.locator(".seating-result")).to_contain_text("Garden")
        card = host.locator(".seating-table-card")
        card.get_by_text("Edit table", exact=True).click()
        card.get_by_role("button", name="Delete table").click()
        expect(host.locator(".seating-table-card")).to_have_count(0)
        guest.reload()
        expect(guest.get_by_role("heading", name="Seating details are on their way.")).to_be_visible()

        nav = guest.get_by_role("navigation", name="Wedding guest navigation")
        nav.get_by_role("link", name="Share photos", exact=True).click()
        expect(guest.get_by_role("heading", name=re.compile("Every little moment"))).to_be_visible()
        guest.get_by_role("navigation", name="Wedding guest navigation").get_by_role("link", name="Gallery", exact=True).click()
        expect(guest.get_by_role("heading", name=re.compile("Through your eyes"))).to_be_visible()
        guest.get_by_role("navigation", name="Wedding guest navigation").get_by_role("link", name="Welcome", exact=True).click()
        expect(guest.locator(".experience-actions")).to_be_visible()
    finally:
        host.close(); guest.close()


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_guest_seating_handles_long_labels_and_large_text(browser, family_site, app, width, tmp_path):
    url, family_id = family_site
    with app.app_context():
        db.session.get(Invitation, family_id).display_name = "Alexandria & Christopher Brown–Lawrence Family and Loved Ones"
        table = SeatingTable(event_id="reception", name="Garden Terrace — Beside the East Courtyard Entrance")
        db.session.add(table); db.session.flush()
        db.session.add(SeatingAssignment(invitation_id=family_id, event_id="reception", table_id=table.table_id, updated_by="fixture"))
        db.session.commit()
    page = page_for(browser, width)
    try:
        page.emulate_media(color_scheme="light", reduced_motion="reduce")
        page.goto(f"{url}/photos/{TOKEN}/seating?event=reception&q=brown")
        expect(page.locator(".seating-result")).to_contain_text("Garden Terrace")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
        page.screenshot(path=str(tmp_path / f"seating-{width}.png"), full_page=True)
        # Double actual rendered font sizes to exercise large text independently
        # of browser zoom/device pixel ratio.
        page.evaluate("""() => {
            const elements = [...document.querySelectorAll('h1,h2,p,a,label>span,button,input,select,.experience-pagination span')];
            const sizes = elements.map(el => parseFloat(getComputedStyle(el).fontSize));
            elements.forEach((el, i) => { el.style.fontSize = `${sizes[i] * 2}px`; });
        }""")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"), page.evaluate("""() => [...document.querySelectorAll('body *')].filter(e => e.scrollWidth > e.clientWidth + 2).map(e => ({tag:e.tagName, cls:e.className, right:e.getBoundingClientRect().right, scroll:e.scrollWidth, client:e.clientWidth, text:e.textContent.slice(0,60)}))""")
        page.get_by_role("searchbox", name="Your name or family name").focus()
        expect(page.get_by_role("searchbox", name="Your name or family name")).to_be_focused()
        page.get_by_role("searchbox", name="Your name or family name").press("Enter")
        expect(page.locator(".seating-result")).to_contain_text("Garden Terrace")
    finally:
        page.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_solid_control_preference_and_system_reduced_effects(browser, family_site, scheme):
    url, _ = family_site
    page = page_for(browser, 1440)
    try:
        page.emulate_media(color_scheme=scheme)
        page.goto(f"{url}/photos/{TOKEN}/welcome")
        toggle = page.get_by_role("button", name="Solid controls", exact=True)
        expect(toggle).to_be_visible()
        expect(toggle).to_have_attribute("aria-pressed", "false")
        toggle.click()
        expect(toggle).to_have_attribute("aria-pressed", "true")
        assert page.locator(".experience-nav").evaluate("el => getComputedStyle(el).backdropFilter") == "none"
        page.reload()
        expect(page.get_by_role("button", name="Solid controls", exact=True)).to_have_attribute("aria-pressed", "true")
        for label in ["Share photos", "Gallery", "Find table", "Welcome"]:
            page.get_by_role("navigation", name="Wedding guest navigation").get_by_role("link", name=label, exact=True).click()
            expect(page.get_by_role("button", name="Solid controls", exact=True)).to_have_attribute("aria-pressed", "true")
            assert page.locator(".experience-nav").evaluate("el => getComputedStyle(el).backdropFilter") == "none"
        page.emulate_media(contrast="more", forced_colors="active", reduced_motion="reduce")
        assert page.locator(".experience-nav").evaluate("el => getComputedStyle(el).backdropFilter") == "none"
        expect(page.get_by_role("link", name="Find table", exact=True)).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
    finally:
        page.close()
