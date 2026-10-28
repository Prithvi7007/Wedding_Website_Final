from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from urllib.parse import quote_plus, urlencode

from app.repositories.events import AllowedEvent


def _format_date(value) -> str:
    return f"{value.strftime('%A, %B')} {value.day}, {value.year}"


def _format_time(value) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def _calendar_timestamp(event: AllowedEvent, field_name: str) -> str:
    value = getattr(event, field_name)
    combined = datetime.combine(event.event_date, value)
    return combined.strftime("%Y%m%dT%H%M%S")


def _theme_for(title: str) -> str:
    normalized = title.casefold()
    if "haldi" in normalized:
        return "haldi"
    if "telugu" in normalized or "hindu" in normalized:
        return "hindu"
    if any(word in normalized for word in ("church", "christian", "reception")):
        return "christian"
    return "neutral"


def present_event(event: AllowedEvent) -> dict:
    theme = _theme_for(event.title)
    theme_content = {
        "haldi": {
            "timeline_title": "Haldi",
            "kicker": "A joyful pre-wedding celebration",
            "attire_stem": "attire-haldi",
        },
        "hindu": {
            "timeline_title": "Telugu Wedding",
            "kicker": "Traditional Telugu ceremony, Lunch and blessings",
            "attire_stem": "attire-hindu",
        },
        "christian": {
            "timeline_title": "Wedding & Reception",
            "kicker": "Ceremony, dinner, dancing, and celebration",
            "attire_stem": "attire-reception",
        },
        "neutral": {
            "timeline_title": event.title,
            "kicker": event.description or "A celebration with family and friends",
            "attire_stem": None,
        },
    }[theme]

    google_calendar_params = {
        "action": "TEMPLATE",
        "text": event.title,
        "dates": (
            f"{_calendar_timestamp(event, 'start_time')}/"
            f"{_calendar_timestamp(event, 'end_time')}"
        ),
        "details": event.description or "",
        "location": event.location,
        "ctz": event.timezone or "America/New_York",
    }

    result = asdict(event)
    result.update(
        theme=theme,
        date_display=_format_date(event.event_date),
        time_display=_format_time(event.start_time),
        time_range=(
            f"{_format_time(event.start_time)} – {_format_time(event.end_time)}"
        ),
        timeline_title=theme_content["timeline_title"],
        kicker=theme_content["kicker"],
        attire_stem=theme_content["attire_stem"],
        directions_link=(
            "https://www.google.com/maps/search/?api=1&query="
            + quote_plus(event.location)
        ),
        google_calendar_link=(
            "https://calendar.google.com/calendar/render?"
            + urlencode(google_calendar_params)
        ),
    )
    return result


def present_events(events: list[AllowedEvent]) -> list[dict]:
    return [present_event(event) for event in events]


def present_welcome_weekend(events: list[AllowedEvent], saved_rsvps: dict) -> list[dict]:
    """Describe only permitted events, never unrelated RSVP records."""
    previews = []
    for event in events:
        saved = saved_rsvps.get(event.event_id)
        response = saved.attending if saved is not None else None
        if response == "Yes":
            status = "Attending"
            if saved.guest_count:
                suffix = "guest" if saved.guest_count == 1 else "guests"
                status += f" · {saved.guest_count} {suffix}"
        elif response == "No":
            status = "Unable to attend"
        elif response == "Maybe":
            status = "Maybe · Response noted"
        else:
            status = "Awaiting your RSVP"
        previews.append({
            "event_id": event.event_id,
            "title": event.title,
            "date_display": _format_date(event.event_date),
            "month": event.event_date.strftime("%b"),
            "day": event.event_date.day,
            "venue": event.venue_name or event.location,
            "status": status,
            "status_kind": response.lower() if response else "pending",
            "is_pending": response is None,
        })
    return previews
