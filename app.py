import os
from pathlib import Path
from datetime import datetime
from urllib.parse import urlencode, quote_plus

import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, Response, jsonify

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent

if load_dotenv:
    load_dotenv(BASE_DIR / ".env")


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "temporary-dev-secret-key-change-this")


# =============================
# DATABASE
# =============================

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "wedding_db"),
        user=os.getenv("DB_USER", "wedding_user"),
        password=os.getenv("DB_PASSWORD"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )


def fetch_one(query, params=None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            return cur.fetchone()


def fetch_all(query, params=None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            return cur.fetchall()


def execute_query(query, params=None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
        conn.commit()


# =============================
# HELPERS
# =============================

def format_date(value):
    if not value:
        return ""

    return value.strftime("%B %d, %Y").replace(" 0", " ")


def format_time(value):
    if not value:
        return ""

    return value.strftime("%I:%M %p").lstrip("0")


def format_date_time_line(event_date, start_time):
    if not event_date or not start_time:
        return ""

    weekday = event_date.strftime("%A")
    return f"{weekday} • {format_date(event_date)} • {format_time(start_time)}"


def calendar_timestamp(event, time_key):
    combined = datetime.combine(event["event_date"], event[time_key])
    return combined.strftime("%Y%m%dT%H%M%S")


def build_google_calendar_link(event):
    calendar_start = calendar_timestamp(event, "start_time")
    calendar_end = calendar_timestamp(event, "end_time")

    calendar_params = {
        "action": "TEMPLATE",
        "text": event["title"],
        "dates": f"{calendar_start}/{calendar_end}",
        "details": event.get("description") or "",
        "location": event.get("location") or "",
        "ctz": event.get("timezone") or "America/New_York"
    }

    return "https://calendar.google.com/calendar/render?" + urlencode(calendar_params)


def build_directions_link(event):
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(event.get("location") or "")


def escape_ics_text(text):
    if not text:
        return ""

    return (
        text.replace("\\", "\\\\")
            .replace(",", "\\,")
            .replace(";", "\\;")
            .replace("\n", "\\n")
    )


def get_current_invitation():
    invitation_id = session.get("invitation_id")

    if not invitation_id:
        return None

    invitation = fetch_one(
        """
        SELECT
            invitation_id,
            represent_side,
            first_name,
            last_name,
            partner_name,
            display_name,
            guest_group,
            message,
            invite_token,
            email,
            phone,
            is_active
        FROM invitations
        WHERE invitation_id = %s
          AND is_active = TRUE
        """,
        (invitation_id,)
    )

    if not invitation:
        session.clear()
        return None

    invitation["name"] = invitation["display_name"]
    return invitation


def get_allowed_events(invitation_id):
    rows = fetch_all(
        """
        SELECT
            e.event_id,
            e.title,
            e.event_date,
            e.start_time,
            e.end_time,
            e.timezone,
            e.short_date,
            e.venue_name,
            e.location,
            e.description,
            e.attire_image,
            e.attire_heading,
            e.attire_subheading,
            e.attire,
            e.display_order,
            p.max_guests
        FROM invitation_event_permissions p
        JOIN events e
            ON p.event_id = e.event_id
        WHERE p.invitation_id = %s
        ORDER BY e.display_order
        """,
        (invitation_id,)
    )

    events = []

    for row in rows:
        event = dict(row)

        event["id"] = event["event_id"]
        event["date"] = format_date(event["event_date"])
        event["time"] = format_time(event["start_time"])
        event["date_time_line"] = format_date_time_line(event["event_date"], event["start_time"])
        event["calendar_link"] = build_google_calendar_link(event)
        event["directions_link"] = build_directions_link(event)

        events.append(event)

    return events


def get_event_for_invitation(invitation_id, event_id):
    return fetch_one(
        """
        SELECT
            e.event_id,
            e.title,
            e.event_date,
            e.start_time,
            e.end_time,
            e.timezone,
            e.short_date,
            e.venue_name,
            e.location,
            e.description,
            e.attire_image,
            e.attire_heading,
            e.attire_subheading,
            e.attire,
            p.max_guests
        FROM invitation_event_permissions p
        JOIN events e
            ON p.event_id = e.event_id
        WHERE p.invitation_id = %s
          AND e.event_id = %s
        """,
        (invitation_id, event_id)
    )


def get_saved_rsvps_for_invitation(invitation_id):
    rows = fetch_all(
        """
        SELECT
            event_id,
            attending,
            guest_count,
            notes
        FROM rsvps
        WHERE invitation_id = %s
        """,
        (invitation_id,)
    )

    saved = {}

    for row in rows:
        saved[row["event_id"]] = {
            "attending": row["attending"],
            "guest_count": row["guest_count"],
            "notes": row["notes"]
        }

    return saved


def get_rsvp_ui_status(attending):
    if attending == "Yes":
        return {
            "status_class": "status-yes",
            "badge_class": "badge-yes",
            "badge_text": "Confirmed",
            "heading_text": "We are delighted you'll be joining us.",
            "celebrate": True
        }

    if attending == "No":
        return {
            "status_class": "status-no",
            "badge_class": "badge-no",
            "badge_text": "Declined",
            "heading_text": "We will miss you at this event.",
            "celebrate": False
        }

    return {
        "status_class": "status-maybe",
        "badge_class": "badge-maybe",
        "badge_text": "Maybe",
        "heading_text": "Thank you for letting us know.",
        "celebrate": False
    }


def wants_json_response():
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def normalize_tab(tab):
    allowed_tabs = ["welcome", "schedule", "travel", "registry", "qa"]

    if tab in allowed_tabs:
        return tab

    return "welcome"


# =============================
# ROUTES
# =============================

@app.route("/")
def home():
    return render_template(
        "index.html",
        redirect_url=None,
        guest_name=None,
        invalid_invite=False
    )


@app.route("/invite/<invite_token>")
def invite(invite_token):
    invitation = fetch_one(
        """
        SELECT
            invitation_id,
            display_name,
            invite_token,
            is_active
        FROM invitations
        WHERE invite_token = %s
          AND is_active = TRUE
        """,
        (invite_token,)
    )

    if not invitation:
        return render_template(
            "index.html",
            redirect_url=None,
            guest_name=None,
            invalid_invite=True
        ), 404

    session.clear()
    session["invitation_id"] = invitation["invitation_id"]
    session["invite_token"] = invitation["invite_token"]

    return render_template(
        "index.html",
        redirect_url=url_for("dashboard", login="success"),
        guest_name=invitation["display_name"],
        invalid_invite=False
    )


@app.route("/dashboard")
def dashboard():
    invitation = get_current_invitation()

    if not invitation:
        return redirect(url_for("home"))

    celebrate = request.args.get("celebrate")
    celebrate_event_id = request.args.get("event")
    login_effect = request.args.get("login")

    active_tab = normalize_tab(request.args.get("tab", "welcome"))

    if celebrate == "yes":
        active_tab = "schedule"

    events = get_allowed_events(invitation["invitation_id"])
    saved_rsvps = get_saved_rsvps_for_invitation(invitation["invitation_id"])

    return render_template(
        "dashboard.html",
        guest=invitation,
        events=events,
        saved_rsvps=saved_rsvps,
        celebrate=celebrate,
        celebrate_event_id=celebrate_event_id,
        login_effect=login_effect,
        active_tab=active_tab
    )


@app.route("/rsvp", methods=["POST"])
def save_rsvp():
    invitation = get_current_invitation()
    wants_json = wants_json_response()

    if not invitation:
        if wants_json:
            return jsonify({
                "success": False,
                "message": "Your session expired. Please open your private invitation link again."
            }), 401

        return redirect(url_for("home"))

    event_id = request.form.get("event_id", "").strip()

    event = get_event_for_invitation(invitation["invitation_id"], event_id)

    if not event:
        if wants_json:
            return jsonify({
                "success": False,
                "message": "You are not invited to this event."
            }), 403

        return redirect(url_for("dashboard", tab="schedule") + "#schedule")

    attending = request.form.get("attending", "").strip()
    notes = request.form.get("notes", "").strip()

    if attending not in ["Yes", "No", "Maybe"]:
        if wants_json:
            return jsonify({
                "success": False,
                "message": "Please select Yes, No, or Maybe."
            }), 400

        return redirect(url_for("dashboard", tab="schedule") + "#schedule")

    try:
        guest_count = int(request.form.get("guest_count", "0"))
    except ValueError:
        guest_count = 0

    max_guests = event["max_guests"]

    if attending == "No":
        guest_count = 0
    else:
        guest_count = max(0, min(guest_count, max_guests))

    execute_query(
        """
        INSERT INTO rsvps (
            invitation_id,
            event_id,
            attending,
            guest_count,
            notes
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (invitation_id, event_id)
        DO UPDATE SET
            attending = EXCLUDED.attending,
            guest_count = EXCLUDED.guest_count,
            notes = EXCLUDED.notes,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            invitation["invitation_id"],
            event_id,
            attending,
            guest_count,
            notes
        )
    )

    status = get_rsvp_ui_status(attending)

    if wants_json:
        return jsonify({
            "success": True,
            "event_id": event["event_id"],
            "event_title": event["title"],
            "attending": attending,
            "guest_count": guest_count,
            "notes": notes,
            "status_class": status["status_class"],
            "badge_class": status["badge_class"],
            "badge_text": status["badge_text"],
            "heading_text": status["heading_text"],
            "celebrate": status["celebrate"]
        })

    if attending == "Yes":
        return redirect(
            url_for("dashboard", tab="schedule", celebrate="yes", event=event_id) + "#schedule"
        )

    return redirect(url_for("dashboard", tab="schedule") + "#schedule")


@app.route("/calendar/<event_id>.ics")
def apple_calendar_event(event_id):
    invitation = get_current_invitation()

    if not invitation:
        return redirect(url_for("home"))

    event = get_event_for_invitation(invitation["invitation_id"], event_id)

    if not event:
        return redirect(url_for("dashboard"))

    calendar_start = calendar_timestamp(event, "start_time")
    calendar_end = calendar_timestamp(event, "end_time")

    title = escape_ics_text(event["title"])
    description = escape_ics_text(event.get("description") or "")
    location = escape_ics_text(event.get("location") or "")
    timezone = event.get("timezone") or "America/New_York"

    ics_content = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Adlin and Prithvi Wedding//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{event_id}@adlin-prithvi-wedding",
        f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;TZID={timezone}:{calendar_start}",
        f"DTEND;TZID={timezone}:{calendar_end}",
        f"SUMMARY:{title}",
        f"DESCRIPTION:{description}",
        f"LOCATION:{location}",
        "END:VEVENT",
        "END:VCALENDAR",
        ""
    ])

    filename = f"{event_id}.ics"

    return Response(
        ics_content,
        mimetype="text/calendar",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
