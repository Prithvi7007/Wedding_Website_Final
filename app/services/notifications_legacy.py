"""Email notification service for wedding RSVP changes.

This module is intentionally independent of Flask and PostgreSQL. The RSVP
route should call ``send_rsvp_notification`` only after the database commit
succeeds.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Any, Mapping, Sequence

import resend

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RSVPState:
    """A normalized snapshot of one RSVP record."""

    attending: str
    guest_count: int
    notes: str = ""


@dataclass(frozen=True)
class RSVPNotification:
    """Information required to build an RSVP alert email."""

    guest_name: str
    event_title: str
    current: RSVPState
    previous: RSVPState | None = None
    submitted_at: datetime | None = None

    @property
    def is_update(self) -> bool:
        return self.previous is not None


@dataclass(frozen=True)
class NotificationResult:
    """Outcome returned to the Flask route for logging/observability."""

    sent: bool
    message_id: str | None = None
    error: str | None = None


def _recipient_list(raw_recipients: str | None = None) -> list[str]:
    value = raw_recipients if raw_recipients is not None else os.getenv("RSVP_EMAIL_TO", "")
    return [address.strip() for address in value.split(",") if address.strip()]


def _status_label(attending: str) -> str:
    normalized = attending.strip().lower()
    if normalized == "yes":
        return "Yes — Attending"
    if normalized == "no":
        return "No — Declined"
    if normalized == "maybe":
        return "Maybe"
    return attending.strip() or "Not provided"


def _format_timestamp(value: datetime | None) -> str:
    submitted_at = value or datetime.now().astimezone()

    month = submitted_at.strftime("%B")
    day = submitted_at.day
    year = submitted_at.year
    time_text = submitted_at.strftime("%I:%M %p").lstrip("0")
    timezone_text = submitted_at.tzname() or ""

    formatted = f"{month} {day}, {year} at {time_text}"

    if timezone_text:
        formatted += f" {timezone_text}"

    return formatted


def _state_summary(state: RSVPState) -> str:
    return f"{_status_label(state.attending)} · {state.guest_count} guest(s)"


def _changed_fields(previous: RSVPState | None, current: RSVPState) -> list[str]:
    if previous is None:
        return []

    changes: list[str] = []
    if previous.attending != current.attending:
        changes.append("Response")
    if previous.guest_count != current.guest_count:
        changes.append("Guest count")
    if previous.notes.strip() != current.notes.strip():
        changes.append("Notes")
    return changes


def build_rsvp_email(notification: RSVPNotification) -> tuple[str, str, str]:
    """Return ``(subject, html, text)`` for a new or updated RSVP."""

    action = "RSVP Updated" if notification.is_update else "New RSVP Received"
    subject = f"{action} — {notification.event_title} — {notification.guest_name}"

    safe_guest = escape(notification.guest_name)
    safe_event = escape(notification.event_title)
    safe_notes = escape(notification.current.notes.strip()) if notification.current.notes.strip() else "None provided"
    current_status = escape(_status_label(notification.current.attending))
    submitted_at = escape(_format_timestamp(notification.submitted_at))

    previous_html = ""
    previous_text = ""
    changes = _changed_fields(notification.previous, notification.current)

    if notification.previous is not None:
        previous_summary = escape(_state_summary(notification.previous))
        changed_label = escape(", ".join(changes) if changes else "No material values changed")
        previous_html = f"""
            <tr>
                <td style="padding:12px 0;color:#765847;vertical-align:top;">Previous RSVP</td>
                <td style="padding:12px 0;font-weight:700;">{previous_summary}</td>
            </tr>
            <tr>
                <td style="padding:12px 0;color:#765847;vertical-align:top;">Changed</td>
                <td style="padding:12px 0;font-weight:700;">{changed_label}</td>
            </tr>
        """
        previous_text = (
            f"Previous RSVP: {_state_summary(notification.previous)}\n"
            f"Changed: {', '.join(changes) if changes else 'No material values changed'}\n"
        )

    html = f"""
    <!doctype html>
    <html lang="en">
      <body style="margin:0;background:#f4ead8;padding:24px;">
        <div style="max-width:640px;margin:0 auto;background:#fffaf1;border:1px solid #d8c19b;border-radius:18px;overflow:hidden;font-family:Georgia,'Times New Roman',serif;color:#2b1a12;">
          <div style="padding:30px 34px 22px;background:linear-gradient(135deg,#f6e8cf,#ead0a5);border-bottom:1px solid #d8c19b;">
            <div style="font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#8a6526;">Adlin &amp; Prithvi Wedding</div>
            <h1 style="margin:10px 0 0;font-size:30px;line-height:1.2;">{escape(action)}</h1>
          </div>

          <div style="padding:26px 34px 32px;">
            <table role="presentation" style="width:100%;border-collapse:collapse;font-size:16px;line-height:1.5;">
              <tr>
                <td style="padding:12px 0;color:#765847;vertical-align:top;width:38%;">Guest</td>
                <td style="padding:12px 0;font-weight:700;">{safe_guest}</td>
              </tr>
              <tr>
                <td style="padding:12px 0;color:#765847;vertical-align:top;">Event</td>
                <td style="padding:12px 0;font-weight:700;">{safe_event}</td>
              </tr>
              {previous_html}
              <tr>
                <td style="padding:12px 0;color:#765847;vertical-align:top;">Current response</td>
                <td style="padding:12px 0;font-weight:700;">{current_status}</td>
              </tr>
              <tr>
                <td style="padding:12px 0;color:#765847;vertical-align:top;">Guest count</td>
                <td style="padding:12px 0;font-weight:700;">{notification.current.guest_count}</td>
              </tr>
              <tr>
                <td style="padding:12px 0;color:#765847;vertical-align:top;">Notes</td>
                <td style="padding:12px 0;font-weight:700;white-space:pre-wrap;">{safe_notes}</td>
              </tr>
              <tr>
                <td style="padding:12px 0;color:#765847;vertical-align:top;">Submitted</td>
                <td style="padding:12px 0;font-weight:700;">{submitted_at}</td>
              </tr>
            </table>
          </div>
        </div>
      </body>
    </html>
    """

    text = (
        f"Adlin & Prithvi Wedding\n\n"
        f"{action}\n\n"
        f"Guest: {notification.guest_name}\n"
        f"Event: {notification.event_title}\n"
        f"{previous_text}"
        f"Current response: {_status_label(notification.current.attending)}\n"
        f"Guest count: {notification.current.guest_count}\n"
        f"Notes: {notification.current.notes.strip() or 'None provided'}\n"
        f"Submitted: {_format_timestamp(notification.submitted_at)}\n"
    )

    return subject, html, text


def send_rsvp_notification(
    notification: RSVPNotification,
    *,
    api_key: str | None = None,
    sender: str | None = None,
    recipients: Sequence[str] | None = None,
) -> NotificationResult:
    """Send an RSVP alert through Resend without raising into the RSVP route.

    Missing configuration or provider failures are logged and returned as a
    failed result. This ensures that an email outage never rolls back or blocks
    a successfully saved RSVP.
    """

    resolved_api_key = api_key or os.getenv("RESEND_API_KEY")
    resolved_sender = sender or os.getenv(
        "RSVP_EMAIL_FROM",
        "Adlin & Prithvi RSVP <rsvp@adlinprithvi.cloud>",
    )
    resolved_recipients = list(recipients) if recipients is not None else _recipient_list()

    if not resolved_api_key:
        message = "RESEND_API_KEY is not configured"
        logger.warning("RSVP notification skipped: %s.", message)
        return NotificationResult(sent=False, error=message)

    if not resolved_recipients:
        message = "RSVP_EMAIL_TO is not configured"
        logger.warning("RSVP notification skipped: %s.", message)
        return NotificationResult(sent=False, error=message)

    subject, html, text = build_rsvp_email(notification)
    resend.api_key = resolved_api_key

    try:
        response: Mapping[str, Any] | Any = resend.Emails.send(
            {
                "from": resolved_sender,
                "to": resolved_recipients,
                "subject": subject,
                "html": html,
                "text": text,
            }
        )

        if isinstance(response, Mapping):
            message_id = response.get("id")
        else:
            message_id = getattr(response, "id", None)

        logger.info(
            "RSVP notification sent for guest=%s event=%s message_id=%s",
            notification.guest_name,
            notification.event_title,
            message_id,
        )
        return NotificationResult(sent=True, message_id=message_id)

    except Exception as exc:  # Provider/network errors must not break RSVP saving.
        logger.exception(
            "Failed to send RSVP notification for guest=%s event=%s",
            notification.guest_name,
            notification.event_title,
        )
        return NotificationResult(sent=False, error=str(exc))