from pathlib import Path


def test_regular_event_cards_show_only_start_time():
    template = Path("app/templates/tabs/schedule.html").read_text(
        encoding="utf-8"
    )

    assert "{{ event.time_display }}" in template
    assert "{{ event.time_range }}" not in template


def test_christian_event_displays_both_times():
    template = Path("app/templates/tabs/schedule.html").read_text(
        encoding="utf-8"
    )

    assert "event.theme == 'christian'" in template
    assert "<strong>6:00 PM</strong>" in template
    assert "<span>Wedding</span>" in template
    assert "<strong>7:00 PM</strong>" in template
    assert "<span>Reception</span>" in template


def test_christian_event_times_are_styled():
    css = Path("app/static/css/schedule.css").read_text(encoding="utf-8")

    assert "EVENT TIME DISPLAY V2" in css
    assert ".event-time-pair" in css
    assert ".event-time-entry" in css
