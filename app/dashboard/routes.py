from __future__ import annotations

from datetime import datetime, timezone

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
from app.dashboard.presenters import present_event, present_events
from app.repositories import EventRepository, RSVPRepository
from app.services import current_invitation
from app.services.notifications_legacy import (
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

    # Welcome and information tabs do not need RSVP/event queries. The schedule
    # fragment loads this data only when the guest actually opens that tab.
    if active_tab == "schedule":
        allowed_events = EventRepository.allowed_for_invitation(
            invitation.invitation_id
        )
        context["events"] = present_events(allowed_events)
        context["saved_rsvps"] = RSVPRepository.saved_for_invitation(
            invitation.invitation_id
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
    return (
        value.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _calendar_timestamp(event, field_name: str) -> str:
    combined = datetime.combine(event.event_date, getattr(event, field_name))
    return combined.strftime("%Y%m%dT%H%M%S")


@dashboard_bp.get("")
def shell():
    invitation = current_invitation()
    if invitation is None:
        return redirect(url_for("invitations.home"))

    active_tab = normalize_tab(request.args.get("tab"))
    context = _dashboard_context(active_tab)
    context.update(login_effect=request.args.get("login"))

    return render_template("dashboard/shell.html", **context)


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
    notification_result = send_rsvp_notification(notification)

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

    timezone_name = event.timezone or "America/New_York"
    calendar_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Adlin and Prithvi Wedding//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{event.event_id}@adlinprithvi.cloud",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        (
            f"DTSTART;TZID={timezone_name}:"
            f"{_calendar_timestamp(event, 'start_time')}"
        ),
        (
            f"DTEND;TZID={timezone_name}:"
            f"{_calendar_timestamp(event, 'end_time')}"
        ),
        f"SUMMARY:{_escape_ics_text(event.title)}",
        f"DESCRIPTION:{_escape_ics_text(event.description)}",
        f"LOCATION:{_escape_ics_text(event.location)}",
        "END:VEVENT",
        "END:VCALENDAR",
        "",
    ]
    calendar_content = "\r\n".join(calendar_lines)

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
