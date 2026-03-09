"""
database.py - SQLite database management for JobTracker
Supports: OA details, referral info, assessment links, multi-account
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "jobs.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS job_applications (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            company             TEXT NOT NULL,
            role                TEXT NOT NULL,
            gmail_account       TEXT NOT NULL,
            applied_date        TEXT,
            status              TEXT DEFAULT 'Applied',
            stage               TEXT DEFAULT 'Applied',
            important_dates     TEXT DEFAULT '',
            last_updated        TEXT,
            thread_id           TEXT,
            notes               TEXT DEFAULT '',
            email_subject       TEXT DEFAULT '',
            job_url             TEXT DEFAULT '',
            referred_by         TEXT DEFAULT '',
            referral_date       TEXT DEFAULT '',
            oa_platform         TEXT DEFAULT '',
            oa_link             TEXT DEFAULT '',
            oa_deadline         TEXT DEFAULT '',
            oa_duration         TEXT DEFAULT '',
            oa_details          TEXT DEFAULT '',
            interview_link      TEXT DEFAULT '',
            interview_date      TEXT DEFAULT '',
            interview_details   TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS email_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id          INTEGER,
            event_date      TEXT,
            event_type      TEXT,
            subject         TEXT,
            snippet         TEXT,
            message_id      TEXT UNIQUE,
            extracted_links TEXT DEFAULT '',
            extracted_dates TEXT DEFAULT '',
            raw_details     TEXT DEFAULT '',
            sender_full     TEXT DEFAULT '',
            body_text       TEXT DEFAULT '',
            FOREIGN KEY (job_id) REFERENCES job_applications(id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key     TEXT PRIMARY KEY,
            value   TEXT
        );

        CREATE TABLE IF NOT EXISTS scan_log (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_time           TEXT,
            account             TEXT,
            emails_scanned      INTEGER,
            new_applications    INTEGER,
            updates_found       INTEGER,
            status              TEXT
        );
    """)
    _migrate(c)
    conn.commit()
    conn.close()


def _migrate(c):
    """Add new columns to existing DB without breaking old data."""
    new_columns = [
        ("job_applications", "referred_by",         "TEXT DEFAULT ''"),
        ("job_applications", "referral_date",        "TEXT DEFAULT ''"),
        ("job_applications", "oa_platform",          "TEXT DEFAULT ''"),
        ("job_applications", "oa_link",              "TEXT DEFAULT ''"),
        ("job_applications", "oa_deadline",          "TEXT DEFAULT ''"),
        ("job_applications", "oa_duration",          "TEXT DEFAULT ''"),
        ("job_applications", "oa_details",           "TEXT DEFAULT ''"),
        ("job_applications", "interview_link",       "TEXT DEFAULT ''"),
        ("job_applications", "interview_date",       "TEXT DEFAULT ''"),
        ("job_applications", "interview_details",    "TEXT DEFAULT ''"),
        ("email_events",     "extracted_links",      "TEXT DEFAULT ''"),
        ("email_events",     "extracted_dates",      "TEXT DEFAULT ''"),
        ("email_events",     "raw_details",          "TEXT DEFAULT ''"),
        ("email_events",     "sender_full",          "TEXT DEFAULT ''"),
        ("email_events",     "body_text",            "TEXT DEFAULT ''"),
    ]
    for table, col, col_def in new_columns:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
        except Exception:
            pass


# ── Fetch ──────────────────────────────────────────────────────────────────

def get_all_jobs(filter_status=None, search_query=None, filter_account=None):
    conn = get_connection()
    c = conn.cursor()
    query = "SELECT * FROM job_applications"
    params = []
    conditions = []
    if filter_status and filter_status != "All":
        conditions.append("status = ?")
        params.append(filter_status)
    if search_query:
        conditions.append("(company LIKE ? OR role LIKE ? OR notes LIKE ? OR referred_by LIKE ?)")
        params.extend([f"%{search_query}%"] * 4)
    if filter_account and filter_account != "All Accounts":
        conditions.append("gmail_account = ?")
        params.append(filter_account)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY last_updated DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_job_by_id(job_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM job_applications WHERE id = ?", (job_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


# ── Create ─────────────────────────────────────────────────────────────────

def add_job(company, role, gmail_account, applied_date=None, thread_id=None,
            email_subject="", job_url="", notes="",
            referred_by="", referral_date=""):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().strftime("%d-%m-%Y %H:%M")
    if not applied_date:
        applied_date = datetime.now().strftime("%d-%m-%Y")
    c.execute("""
        INSERT INTO job_applications
        (company, role, gmail_account, applied_date, status, stage, last_updated,
         thread_id, email_subject, job_url, notes, referred_by, referral_date)
        VALUES (?, ?, ?, ?, 'Applied', 'Applied', ?, ?, ?, ?, ?, ?, ?)
    """, (company, role, gmail_account, applied_date, now, thread_id,
          email_subject, job_url, notes, referred_by, referral_date))
    job_id = c.lastrowid
    conn.commit()
    conn.close()
    return job_id


# ── Update ─────────────────────────────────────────────────────────────────

def update_job_status(job_id, status=None, stage=None, important_dates=None,
                      notes=None, referred_by=None, referral_date=None,
                      oa_platform=None, oa_link=None, oa_deadline=None,
                      oa_duration=None, oa_details=None,
                      interview_link=None, interview_date=None, interview_details=None):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().strftime("%d-%m-%Y %H:%M")
    updates = ["last_updated = ?"]
    params = [now]

    simple_fields = [
        ("status", status), ("stage", stage), ("notes", notes),
        ("referred_by", referred_by), ("referral_date", referral_date),
        ("oa_platform", oa_platform), ("oa_link", oa_link),
        ("oa_deadline", oa_deadline), ("oa_duration", oa_duration),
        ("oa_details", oa_details),
        ("interview_link", interview_link), ("interview_date", interview_date),
        ("interview_details", interview_details),
    ]
    for field, val in simple_fields:
        if val is not None:
            updates.append(f"{field} = ?")
            params.append(val)

    if important_dates:
        c.execute("SELECT important_dates FROM job_applications WHERE id = ?", (job_id,))
        row = c.fetchone()
        existing = row["important_dates"] if row and row["important_dates"] else ""
        existing_list = [d.strip() for d in existing.split(",") if d.strip()]
        new_dates = [d.strip() for d in important_dates.split(",") if d.strip()]
        for d in new_dates:
            if d not in existing_list:
                existing_list.append(d)
        updates.append("important_dates = ?")
        params.append(", ".join(existing_list))

    params.append(job_id)
    c.execute(f"UPDATE job_applications SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def delete_job(job_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM email_events WHERE job_id = ?", (job_id,))
    c.execute("DELETE FROM job_applications WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()


# ── Email Events ───────────────────────────────────────────────────────────

def add_email_event(job_id, event_type, subject, snippet, message_id,
                    event_date=None, extracted_links="", extracted_dates="",
                    raw_details="", sender_full="", body_text=""):
    conn = get_connection()
    c = conn.cursor()
    if not event_date:
        event_date = datetime.now().strftime("%d-%m-%Y")
    try:
        c.execute("""
            INSERT INTO email_events
            (job_id, event_date, event_type, subject, snippet, message_id,
             extracted_links, extracted_dates, raw_details, sender_full, body_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, event_date, event_type, subject, snippet, message_id,
              extracted_links, extracted_dates, raw_details, sender_full, body_text))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()


def get_email_events(job_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM email_events WHERE job_id = ? ORDER BY event_date DESC", (job_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Thread lookup ──────────────────────────────────────────────────────────

def thread_id_exists(thread_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM job_applications WHERE thread_id = ?", (thread_id,))
    row = c.fetchone()
    conn.close()
    return row["id"] if row else None


# ── Settings ───────────────────────────────────────────────────────────────

def get_setting(key, default=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


# ── Stats & Logs ───────────────────────────────────────────────────────────

def log_scan(account, emails_scanned, new_applications, updates_found, status="OK"):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    c.execute("""
        INSERT INTO scan_log (scan_time, account, emails_scanned, new_applications, updates_found, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (now, account, emails_scanned, new_applications, updates_found, status))
    conn.commit()
    conn.close()


def get_stats(account=None):
    conn = get_connection()
    c = conn.cursor()
    stats = {}
    if account and account != "All Accounts":
        c.execute("SELECT COUNT(*) as total FROM job_applications WHERE gmail_account = ?", (account,))
        stats["total"] = c.fetchone()["total"]
        c.execute("SELECT status, COUNT(*) as cnt FROM job_applications WHERE gmail_account = ? GROUP BY status", (account,))
    else:
        c.execute("SELECT COUNT(*) as total FROM job_applications")
        stats["total"] = c.fetchone()["total"]
        c.execute("SELECT status, COUNT(*) as cnt FROM job_applications GROUP BY status")
    for row in c.fetchall():
        stats[row["status"]] = row["cnt"]
    conn.close()
    return stats


def get_recent_scan_logs(limit=10):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM scan_log ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_accounts():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT gmail_account FROM job_applications ORDER BY gmail_account")
    rows = c.fetchall()
    conn.close()
    return [r["gmail_account"] for r in rows]


if __name__ == "__main__":
    # Self-test: called by install.bat to verify DB setup works
    try:
        init_db()
        print("  [OK] Database initialised at:", DB_PATH)
        stats = get_stats()
        print("  [OK] Database readable. Total jobs:", stats.get("total", 0))
    except Exception as e:
        print("  [ERROR]", e)
        raise SystemExit(1)