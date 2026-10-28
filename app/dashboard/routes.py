from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from app.dashboard.media import build_slideshow_manifest
from app.dashboard.presenters import present_event, present_events, present_welcome_weekend
from app.repositories import EventRepository, RSVPRepository
from app.services import current_invitation
from app.services.notifications_legacy import (
    NotificationResult,
    RSVPNotification,
    RSVPState,
    send_rsvp_notification,
)


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")
ALLOWED_TABS = {"welcome", "schedule", "travel", "registry", "qa"}
VALID_ATTENDANCE = {"Yes", "No", "Maybe"}


def normalize_tab(value: str | None) -> str:
    return value if value in ALLOWED_TABS else "welcome"


def _dashboard_context(active_tab: str) -> dict:
    invitation = current_invitation()
    if invitation is None:
        return {}

    context = {
        "invitation": invitation,
        "active_tab": active_tab,
        "slideshow": build_slideshow_manifest(),
        "events": [],
        "saved_rsvps": {},
    }

    # Personalize only Welcome and Schedule. Both use the invitation's
    # approved event permissions, never the unrestricted event catalog.
    if active_tab in ("welcome", "schedule"):
        allowed_events = EventRepository.allowed_for_invitation(
            invitation.invitation_id
        )
        saved_rsvps = RSVPRepository.saved_for_invitation(
            invitation.invitation_id
        )
        if active_tab == "schedule":
            context["events"] = present_events(allowed_events)
            context["saved_rsvps"] = saved_rsvps
        else:
            weekend = present_welcome_weekend(allowed_events, saved_rsvps)
            context["weekend_events"] = weekend
            context["weekend_pending_count"] = sum(
                item["is_pending"] for item in weekend
            )

    return context


def _wants_json() -> bool:
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes.best == "application/json"
    )


def _json_error(message: str, status_code: int):
    return jsonify({"success": False, "message": message}), status_code


def _rsvp_summary(attending: str, guest_count: int) -> str:
    if attending == "Yes":
        suffix = "" if guest_count == 1 else "s"
        return f"Attending · {guest_count} Guest{suffix}"
    if attending == "No":
        return "Unable to Attend"
    return "Maybe · Response Pending"


def _escape_ics_text(value: str | None) -> str:
    if not value:
        return ""
    # Normalize line breaks before escaping, including lone carriage returns.
    return (
        value.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


def _fold_calendar_lines(lines: list[str]) -> str:
    """RFC 5545 content lines are at most 75 UTF-8 octets.

    Fold on Unicode code point boundaries so multibyte names remain intact.
    A continuation line starts with one space, included in its 75-octet limit.
    """
    folded: list[str] = []
    for line in lines:
        if not line:
            folded.append("")
            continue
        part = ""
        used = 0
        for character in line:
            width = len(character.encode("utf-8"))
            if used + width > 75:
                folded.append(part)
                part = " "
                used = 1
            part += character
            used += width
        folded.append(part)
    return "\r\n".join(folded)


def _calendar_timestamp(event, field_name: str) -> str:
    # UTC timestamps are unambiguous across Apple, Outlook and Google clients
    # and do not require a VTIMEZONE component.
    local = datetime.combine(
        event.event_date,
        getattr(event, field_name),
        tzinfo=ZoneInfo(event.timezone or "America/New_York"),
    )
    return local.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@dashboard_bp.get("")
def shell():
    invitation = current_invitation()
    if invitation is None:
        return redirect(url_for("invitations.home"))

    active_tab = normalize_tab(request.args.get("tab"))
    context = _dashboard_context(active_tab)
    context.update(login_effect=request.args.get("login"))

    return render_template("dashboard/shell.html", **context)


@dashboard_bp.get("/preview/guest-v2")
def guest_v2_preview():
    """Isolated, read-only guest redesign preview.

    Uses the same invitation permissions and RSVP snapshots as the live
    dashboard. No new forms or navigation links are added to production.
    """
    invitation = current_invitation()
    if invitation is None:
        return redirect(url_for("invitations.home"))

    allowed_events = EventRepository.allowed_for_invitation(
        invitation.invitation_id
    )
    saved_rsvps = RSVPRepository.saved_for_invitation(invitation.invitation_id)
    weekend = present_welcome_weekend(allowed_events, saved_rsvps)
    response = Response(
        render_template(
            "dashboard/guest_v2_preview.html",
            invitation=invitation,
            events=present_events(allowed_events),
            saved_rsvps=saved_rsvps,
            weekend_events=weekend,
            weekend_pending_count=sum(event["is_pending"] for event in weekend),
        ),
        mimetype="text/html",
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@dashboard_bp.get("/tab/<tab_name>")
def tab_fragment(tab_name: str):
    invitation = current_invitation()
    if invitation is None:
        if _wants_json():
            return _json_error(
                "Your session expired. Open your private invitation link again.",
                401,
            )
        return redirect(url_for("invitations.home"))

    if tab_name not in ALLOWED_TABS:
        abort(404)

    context = _dashboard_context(tab_name)
    response = render_template(f"tabs/{tab_name}.html", **context)
    return response, 200, {"Vary": "X-Requested-With"}


@dashboard_bp.post("/rsvp")
def save_rsvp():
    invitation = current_invitation()
    if invitation is None:
        if _wants_json():
            return _json_error(
                "Your session expired. Open your private invitation link again.",
                401,
            )
        return redirect(url_for("invitations.home"))

    event_id = request.form.get("event_id", "").strip()
    allowed_event = EventRepository.allowed_event_for_invitation(
        invitation.invitation_id,
        event_id,
        for_update=True,
    )
    if allowed_event is None:
        if _wants_json():
            return _json_error("You are not invited to this event.", 403)
        return redirect(url_for("dashboard.shell", tab="schedule"))

    attending = request.form.get("attending", "").strip()
    if attending not in VALID_ATTENDANCE:
        if _wants_json():
            return _json_error("Please select Yes, Maybe, or No.", 400)
        return redirect(url_for("dashboard.shell", tab="schedule"))

    try:
        requested_guest_count = int(request.form.get("guest_count", "0"))
    except (TypeError, ValueError):
        if _wants_json():
            return _json_error("Please choose a valid guest count.", 400)
        return redirect(url_for("dashboard.shell", tab="schedule"))

    if attending == "Yes" and requested_guest_count < 1:
        if _wants_json():
            return _json_error(
                "Please include at least one attending guest.",
                400,
            )
        return redirect(url_for("dashboard.shell", tab="schedule"))

    if attending == "Yes" and allowed_event.max_guests < 1:
        if _wants_json():
            return _json_error(
                "This invitation is not configured for an attending guest.",
                400,
            )
        return redirect(url_for("dashboard.shell", tab="schedule"))

    if attending == "No":
        guest_count = 0
    elif attending == "Yes":
        guest_count = min(requested_guest_count, allowed_event.max_guests)
    else:
        guest_count = max(
            0,
            min(requested_guest_count, allowed_event.max_guests),
        )

    notes = request.form.get("notes", "").strip()[:2000]

    previous_record = RSVPRepository.get_for_event(
        invitation.invitation_id,
        event_id,
    )
    previous_state = None
    if previous_record is not None:
        previous_state = RSVPState(
            attending=previous_record.attending,
            guest_count=previous_record.guest_count,
            notes=previous_record.notes or "",
        )

    try:
        RSVPRepository.save(
            invitation_id=invitation.invitation_id,
            event_id=event_id,
            attending=attending,
            guest_count=guest_count,
            notes=notes,
        )
    except Exception:
        from app.extensions import db

        db.session.rollback()
        current_app.logger.exception(
            "Failed to save RSVP invitation_id=%s event_id=%s",
            invitation.invitation_id,
            event_id,
        )
        if _wants_json():
            return _json_error(
                "We could not save your response. Please try again.",
                500,
            )
        raise

    current_state = RSVPState(
        attending=attending,
        guest_count=guest_count,
        notes=notes,
    )
    notification = RSVPNotification(
        guest_name=invitation.display_name or invitation.first_name or "Wedding Guest",
        event_title=allowed_event.title,
        previous=previous_state,
        current=current_state,
        submitted_at=datetime.now().astimezone(),
    )
    try:
        notification_result = send_rsvp_notification(notification)
    except Exception:
        # A post-commit email error must never look like an unsaved RSVP.
        current_app.logger.exception(
            "Unexpected post-commit email failure invitation_id=%s event_id=%s",
            invitation.invitation_id,
            event_id,
        )
        notification_result = NotificationResult(
            sent=False,
            error="unexpected_notification_failure",
        )

    if notification_result.sent:
        current_app.logger.info(
            "RSVP notification sent invitation_id=%s event_id=%s message_id=%s",
            invitation.invitation_id,
            event_id,
            notification_result.message_id,
        )
    else:
        current_app.logger.warning(
            "RSVP saved but notification was not sent invitation_id=%s "
            "event_id=%s error=%s",
            invitation.invitation_id,
            event_id,
            notification_result.error,
        )

    payload = {
        "success": True,
        "event_id": event_id,
        "event_title": allowed_event.title,
        "attending": attending,
        "guest_count": guest_count,
        "notes": notes,
        "summary_text": _rsvp_summary(attending, guest_count),
        "celebrate": attending == "Yes",
    }
    if _wants_json():
        return jsonify(payload)

    return redirect(url_for("dashboard.shell", tab="schedule"))


def _calendar_event_lines(event, dtstamp: str) -> list[str]:
    """Render the same calendar event for single and weekend exports."""
    return [
        "BEGIN:VEVENT",
        f"UID:{_escape_ics_text(event.event_id)}@adlinprithvi.cloud",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{_calendar_timestamp(event, 'start_time')}",
        f"DTEND:{_calendar_timestamp(event, 'end_time')}",
        f"SUMMARY:{_escape_ics_text(event.title)}",
        f"DESCRIPTION:{_escape_ics_text(event.description)}",
        f"LOCATION:{_escape_ics_text(event.location)}",
        "END:VEVENT",
    ]


@dashboard_bp.get("/calendar/weekend.ics")
def weekend_calendar():
    invitation = current_invitation()
    if invitation is None:
        return redirect(url_for("invitations.home"))

    # Export only events permitted for the signed-in private invitation.
    events = EventRepository.allowed_for_invitation(invitation.invitation_id)
    if not events:
        abort(404)

    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    calendar_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Adlin and Prithvi Wedding//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Adlin and Prithvi Wedding Weekend",
    ]
    for event in events:
        calendar_lines.extend(_calendar_event_lines(event, dtstamp))
    calendar_lines.extend(["END:VCALENDAR", ""])

    return Response(
        _fold_calendar_lines(calendar_lines),
        mimetype="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="adlin-prithvi-weekend.ics"',
            "Cache-Control": "private, no-store",
        },
    )


@dashboard_bp.get("/calendar/<event_id>.ics")
def apple_calendar_event(event_id: str):
    invitation = current_invitation()
    if invitation is None:
        return redirect(url_for("invitations.home"))

    event = EventRepository.allowed_event_for_invitation(
        invitation.invitation_id,
        event_id,
    )
    if event is None:
        abort(404)

    calendar_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Adlin and Prithvi Wedding//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        *_calendar_event_lines(event, datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")),
        "END:VCALENDAR",
        "",
    ]
    calendar_content = _fold_calendar_lines(calendar_lines)

    safe_filename = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in event.event_id
    )
    return Response(
        calendar_content,
        mimetype="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}.ics"',
            "Cache-Control": "private, no-store",
        },
    )
