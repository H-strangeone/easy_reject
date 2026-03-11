"""
calendar_helper.py  —  JobTracker Google Calendar integration
─────────────────────────────────────────────────────────────
Adds OA deadlines, interview dates, and offer deadlines
directly to Google Calendar using the same OAuth credentials
already used for Gmail scanning.

The calendar scope is added alongside the Gmail scope — user
only needs to re-authorise once (token is deleted and recreated).
"""

import os
import re
import sys
from datetime import datetime, timedelta

# ── Try importing Google libs ─────────────────────────────────────────────────
try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database as db

# ── Scopes needed — must match gmail_scanner.py SCOPES ───────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
]

CALENDAR_ID = "primary"   # always use the user's primary calendar


# ──────────────────────────────────────────────────────────────────────────────
#  DATE PARSING  (our dates are stored as dd-mm-yyyy or free text)
# ──────────────────────────────────────────────────────────────────────────────

def _parse_date(date_str: str):
    """
    Try to parse a date string into a datetime object.
    Handles: dd-mm-yyyy, dd/mm/yyyy, yyyy-mm-dd, 'Jan 15 2025', etc.
    Returns datetime or None.
    """
    if not date_str:
        return None
    date_str = date_str.strip()

    formats = [
        "%d-%m-%Y", "%d/%m/%Y",
        "%Y-%m-%d",
        "%d %b %Y", "%d %B %Y",
        "%b %d %Y", "%B %d %Y",
        "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M",
        "%Y-%m-%dT%H:%M",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # Try extracting a date from free text like "by 15 Jan 2025"
    m = re.search(r"(\d{1,2})[/\-\s](\w+)[/\-\s](\d{4})", date_str)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y")
        except ValueError:
            pass

    return None


def _to_rfc3339(dt: datetime, all_day: bool = False) -> dict:
    """Convert datetime to Google Calendar event time dict."""
    if all_day:
        return {"date": dt.strftime("%Y-%m-%d")}
    return {"dateTime": dt.strftime("%Y-%m-%dT%H:%M:00"), "timeZone": "Asia/Kolkata"}


# ──────────────────────────────────────────────────────────────────────────────
#  CALENDAR SERVICE
# ──────────────────────────────────────────────────────────────────────────────

def _get_calendar_service(account_email: str):
    """Build and return a Google Calendar API service for the given account."""
    if not GOOGLE_LIBS_AVAILABLE:
        raise ImportError("Google libraries not installed.")

    # Import here to avoid circular import with gmail_scanner
    import gmail_scanner
    creds = gmail_scanner.get_credentials(account_email,
                                          db.get_setting("credentials_path", ""))
    return build("calendar", "v3", credentials=creds)


# ──────────────────────────────────────────────────────────────────────────────
#  PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

def add_oa_to_calendar(job: dict) -> tuple[bool, str]:
    """
    Add an OA/assessment deadline to Google Calendar.
    job: dict from db.get_job_by_id()
    Returns (success, message)
    """
    company  = job.get("company", "Unknown Company")
    role     = job.get("role", "")
    platform = job.get("oa_platform", "")
    deadline = job.get("oa_deadline", "")
    duration = job.get("oa_duration", "")
    link     = job.get("oa_link", "")
    account  = job.get("gmail_account", "")

    if not deadline:
        return False, "No OA deadline date set — add a deadline date first."
    if not account:
        return False, "No Gmail account linked to this job."

    dt = _parse_date(deadline)
    if not dt:
        return False, f"Couldn't parse date: '{deadline}'. Use dd-mm-yyyy format."

    title = f"🧪 OA: {company}"
    if role:   title += f" — {role}"
    if platform: title += f" ({platform})"

    desc_parts = [f"Online Assessment for {company}"]
    if role:      desc_parts.append(f"Role: {role}")
    if platform:  desc_parts.append(f"Platform: {platform}")
    if duration:  desc_parts.append(f"Duration: {duration}")
    if link:      desc_parts.append(f"Assessment Link: {link}")
    desc_parts.append("\nAdded by JobTracker")
    description = "\n".join(desc_parts)

    # 1-hour block at 9am on the deadline day (or all-day if no time info)
    start_dt = dt.replace(hour=9, minute=0, second=0) if dt.hour == 0 else dt
    end_dt   = start_dt + timedelta(hours=1)

    event = {
        "summary":     title,
        "description": description,
        "start":       _to_rfc3339(start_dt),
        "end":         _to_rfc3339(end_dt),
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup",  "minutes": 60},
                {"method": "popup",  "minutes": 1440},  # 1 day before
            ],
        },
    }
    if link:
        event["source"] = {"title": "Assessment Link", "url": link}

    try:
        service  = _get_calendar_service(account)
        created  = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        event_id = created.get("id", "")
        # Save event ID so we can delete/update it later
        db.update_job_status(job["id"], oa_calendar_event_id=event_id)
        return True, f"✅ Added to Calendar: {title} on {dt.strftime('%d %b %Y')}"
    except Exception as e:
        return False, f"Calendar error: {e}"


def add_interview_to_calendar(job: dict) -> tuple[bool, str]:
    """
    Add an interview to Google Calendar.
    Returns (success, message)
    """
    company = job.get("company", "Unknown Company")
    role    = job.get("role", "")
    date    = job.get("interview_date", "")
    link    = job.get("interview_link", "")
    details = job.get("interview_details", "")
    account = job.get("gmail_account", "")

    if not date:
        return False, "No interview date set — add an interview date first."
    if not account:
        return False, "No Gmail account linked to this job."

    dt = _parse_date(date)
    if not dt:
        return False, f"Couldn't parse date: '{date}'. Use dd-mm-yyyy format."

    title = f"🎤 Interview: {company}"
    if role: title += f" — {role}"

    desc_parts = [f"Interview at {company}"]
    if role:    desc_parts.append(f"Role: {role}")
    if link:    desc_parts.append(f"Meeting Link: {link}")
    if details: desc_parts.append(f"Details: {details}")
    desc_parts.append("\nAdded by JobTracker")
    description = "\n".join(desc_parts)

    start_dt = dt.replace(hour=10, minute=0, second=0) if dt.hour == 0 else dt
    end_dt   = start_dt + timedelta(hours=1)

    event = {
        "summary":     title,
        "description": description,
        "start":       _to_rfc3339(start_dt),
        "end":         _to_rfc3339(end_dt),
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 30},
                {"method": "popup", "minutes": 1440},
            ],
        },
    }
    if link:
        event["conferenceData"] = None  # Zoom/Meet links show as description
        event["source"] = {"title": "Meeting Link", "url": link}

    try:
        service  = _get_calendar_service(account)
        created  = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        event_id = created.get("id", "")
        db.update_job_status(job["id"], interview_calendar_event_id=event_id)
        return True, f"✅ Added to Calendar: {title} on {dt.strftime('%d %b %Y')}"
    except Exception as e:
        return False, f"Calendar error: {e}"


def delete_calendar_event(account_email: str, event_id: str) -> tuple[bool, str]:
    """Delete a calendar event by ID."""
    if not event_id:
        return False, "No event ID."
    try:
        service = _get_calendar_service(account_email)
        service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
        return True, "Calendar event removed."
    except Exception as e:
        return False, f"Could not delete event: {e}"


def check_calendar_scope(account_email: str) -> bool:
    """Return True if the stored token already has the calendar scope."""
    import gmail_scanner
    token_path = gmail_scanner.get_token_path(account_email)
    if not os.path.exists(token_path):
        return False
    try:
        import json
        with open(token_path) as f:
            data = json.load(f)
        scopes = data.get("scopes", [])
        return any("calendar" in s for s in scopes)
    except Exception:
        return False


def reauthorise_with_calendar(account_email: str, credentials_path: str) -> tuple[bool, str]:
    """
    Delete existing token and re-run OAuth so the user grants calendar scope.
    Returns (success, message).
    """
    import gmail_scanner
    token_path = gmail_scanner.get_token_path(account_email)
    if os.path.exists(token_path):
        os.remove(token_path)
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
        return True, f"✅ {account_email} re-authorised with Calendar access."
    except Exception as e:
        return False, f"Re-authorisation failed: {e}"