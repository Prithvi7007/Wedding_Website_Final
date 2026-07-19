from pathlib import Path


def test_travel_tab_has_recommended_hotels_and_no_restaurant_placeholder():
    template = Path("app/templates/tabs/travel.html").read_text(
        encoding="utf-8"
    )

    expected = (
        "Hilton Garden Inn Tampa–Wesley Chapel",
        "Hyatt Place Tampa / Wesley Chapel",
        "Hampton Inn &amp; Suites Tampa Riverview Brandon",
        "Explore Tampa",
        "Historic Ybor City",
        "Getting Around",
        "A Car Is Recommended",
    )

    for text in expected:
        assert text in template

    assert "Favorite Restaurants" not in template
    assert "Selected Eats" not in template
    assert "More recommendations coming soon" not in template


def test_travel_tab_keeps_safe_external_links():
    template = Path("app/templates/tabs/travel.html").read_text(
        encoding="utf-8"
    )

    assert template.count('target="_blank"') >= 10
    assert template.count('rel="noopener noreferrer"') >= 10


def test_travel_refresh_has_responsive_getting_around_grid():
    css = Path("app/static/css/information.css").read_text(
        encoding="utf-8"
    )

    assert "TRAVEL GUIDE REFRESH V2" in css
    assert ".travel-notes-grid" in css
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in css
