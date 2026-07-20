from __future__ import annotations

from typing import Any

from .queries import (
    dashboard_totals,
    event_metrics,
    invitations_without_any_response,
    recent_rsvp_activity,
)


def _percentage(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def build_dashboard_snapshot() -> dict[str, Any]:
    totals = dashboard_totals()
    totals["completion_percentage"] = _percentage(
        totals["responded_invitations"],
        totals["total_active_invitations"],
    )

    events: list[dict[str, Any]] = []
    for row in event_metrics():
        event = dict(row)

        for key in (
            "active_invitation_count",
            "maximum_possible_guests",
            "response_count",
            "confirmed_guest_count",
            "yes_response_count",
            "no_response_count",
            "maybe_response_count",
        ):
            event[key] = int(event[key] or 0)

        event["completion_percentage"] = _percentage(
            event["response_count"],
            event["active_invitation_count"],
        )
        event["capacity_percentage"] = min(
            100.0,
            _percentage(
                event["confirmed_guest_count"],
                event["maximum_possible_guests"],
            ),
        )
        events.append(event)

    return {
        "totals": totals,
        "events": events,
        "recent_activity": recent_rsvp_activity(),
        "unanswered_invitations": invitations_without_any_response(),
    }
