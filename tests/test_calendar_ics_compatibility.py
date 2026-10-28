"""RFC 5545 calendar compatibility without production records."""

from datetime import date, time
from types import SimpleNamespace

from app.dashboard.routes import (
    _calendar_timestamp,
    _escape_ics_text,
    _fold_calendar_lines,
)
from app.extensions import db
from app.models import Event, Invitation, InvitationEventPermission


def test_calendar_utc_conversion_respects_daylight_saving():
    winter = SimpleNamespace(
        event_date=date(2026, 11, 19),
        start_time=time(12, 0),
        timezone="America/New_York",
    )
    summer = SimpleNamespace(
        event_date=date(2026, 7, 19),
        start_time=time(12, 0),
        timezone="America/New_York",
    )
    west_coast = SimpleNamespace(
        event_date=date(2026, 11, 19),
        start_time=time(12, 0),
        timezone="America/Los_Angeles",
    )

    assert _calendar_timestamp(winter, "start_time") == "20261119T170000Z"
    assert _calendar_timestamp(summer, "start_time") == "20260719T160000Z"
    assert _calendar_timestamp(west_coast, "start_time") == "20261119T200000Z"


def test_calendar_line_folding_uses_utf8_octets_not_character_count():
    # 32 emoji alone exceed 75 bytes, despite only 32 code points.
    summary = "SUMMARY:" + ("🎉" * 32) + " Lastname"
    content = _fold_calendar_lines(["BEGIN:VCALENDAR", summary, "END:VCALENDAR", ""])
    lines = content.split("\r\n")

    assert all(len(line.encode("utf-8")) <= 75 for line in lines)
    assert all(line.startswith(" ") for line in lines[2:-2])
    unfolded = content.replace("\r\n ", "")
    assert summary in unfolded
    assert content.endswith("END:VCALENDAR\r\n")


def test_calendar_text_escapes_mixed_newlines_and_punctuation():
    source = "We, celebrate; together\\ here\r\nNext\rLast\nFinal"
    assert _escape_ics_text(source) == (
        r"We\, celebrate\; together\\ here\nNext\nLast\nFinal"
    )


def test_single_and_weekend_calendar_downloads_fold_long_guest_content(client, app):
    title = "Haldi 🎉 " + "Celebration " * 12
    description = "Please join us, friends; with joy 🎉 " + "Kind regards " * 14

    with app.app_context():
        invitation = Invitation(
            first_name="Calendar",
            display_name="Calendar Guest",
            invite_token="calendar-compliance-test",
            is_active=True,
        )
        event = Event(
            event_id="calendar-event",
            title=title,
            event_date=date(2026, 11, 19),
            start_time=time(12, 0),
            end_time=time(15, 0),
            timezone="America/New_York",
            location="Tampa, Florida",
            description=description,
        )
        db.session.add_all([invitation, event])
        db.session.flush()
        db.session.add(
            InvitationEventPermission(
                invitation_id=invitation.invitation_id,
                event_id=event.event_id,
                max_guests=2,
            )
        )
        db.session.commit()

    assert client.post("/invite/calendar-compliance-test/open").status_code == 302

    for url in (
        "/dashboard/calendar/calendar-event.ics",
        "/dashboard/calendar/weekend.ics",
    ):
        result = client.get(url)
        assert result.status_code == 200
        assert result.headers["Cache-Control"].startswith("private, no-store")
        raw = result.data
        assert raw.startswith(b"BEGIN:VCALENDAR\r\n")
        assert raw.endswith(b"END:VCALENDAR\r\n")
        lines = raw.split(b"\r\n")
        assert all(len(line) <= 75 for line in lines)
        assert raw.count(b"BEGIN:VEVENT") == 1
        assert b"DTSTART:20261119T170000Z\r\n" in raw
        assert b"DTEND:20261119T200000Z\r\n" in raw
        assert b"TZID=" not in raw
        unfolded = raw.decode("utf-8").replace("\r\n ", "")
        assert f"SUMMARY:{_escape_ics_text(title)}" in unfolded
        assert f"DESCRIPTION:{_escape_ics_text(description)}" in unfolded
