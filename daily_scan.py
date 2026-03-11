"""
daily_scan.py  —  JobTracker headless daily scanner + email notifier
─────────────────────────────────────────────────────────────────────
Run this script standalone (no GUI needed) to:
  1. Scan all configured Gmail accounts for the last 1 day
  2. Send a summary email via SMTP to your notification address

Usage:
    python daily_scan.py                  # normal run
    python daily_scan.py --days 3         # scan last 3 days instead
    python daily_scan.py --test-email     # just send a test email, no scan

Called automatically by the Windows Task Scheduler (set up via scheduler_setup.py)
or by the app's built-in daily scheduler loop.
"""

import os
import sys
import argparse
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ── Make sure we can import sibling modules ───────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database as db


# ──────────────────────────────────────────────────────────────────────────────
#  SMTP EMAIL SENDER
# ──────────────────────────────────────────────────────────────────────────────

def send_notification_email(subject: str, html_body: str, text_body: str) -> tuple[bool, str]:
    """
    Send an email using SMTP settings stored in the database.
    Returns (success: bool, message: str)
    """
    smtp_host  = db.get_setting("smtp_host",  "").strip()
    smtp_port  = db.get_setting("smtp_port",  "587").strip()
    smtp_user  = db.get_setting("smtp_user",  "").strip()
    smtp_pass  = db.get_setting("smtp_pass",  "").strip()
    smtp_to    = db.get_setting("smtp_to",    "").strip()
    smtp_from  = db.get_setting("smtp_from",  smtp_user).strip() or smtp_user

    if not all([smtp_host, smtp_user, smtp_pass, smtp_to]):
        return False, "SMTP not configured. Add SMTP settings in ⚙ Settings."

    try:
        port = int(smtp_port)
    except ValueError:
        port = 587

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"JobTracker <{smtp_from}>"
    msg["To"]      = smtp_to

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(smtp_host, port, context=context) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, smtp_to, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, smtp_to, msg.as_string())
        return True, f"Email sent to {smtp_to}"
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP auth failed — check username/password (for Gmail use an App Password)"
    except smtplib.SMTPConnectError:
        return False, f"Could not connect to {smtp_host}:{port}"
    except Exception as e:
        return False, f"SMTP error: {e}"


# ──────────────────────────────────────────────────────────────────────────────
#  EMAIL TEMPLATE
# ──────────────────────────────────────────────────────────────────────────────

def build_email(scan_results: dict) -> tuple[str, str, str]:
    """
    Build subject, HTML body, and plain text body from scan results dict.
    scan_results keys:
        new_apps, updates, accounts_scanned, errors,
        new_items: list of {company, role, status, stage}
        timestamp
    """
    new_apps  = scan_results.get("new_apps", 0)
    updates   = scan_results.get("updates", 0)
    errors    = scan_results.get("errors", [])
    new_items = scan_results.get("new_items", [])
    ts        = scan_results.get("timestamp", datetime.now().strftime("%d %b %Y %H:%M"))
    stopped   = scan_results.get("stopped", False)

    # ── Subject ──────────────────────────────────────────────────────────
    if new_apps == 0 and updates == 0:
        subject = f"📊 JobTracker Daily — No new activity ({ts})"
    else:
        parts = []
        if new_apps:  parts.append(f"{new_apps} new")
        if updates:   parts.append(f"{updates} updates")
        subject = f"📊 JobTracker Daily — {', '.join(parts)} ({ts})"

    if stopped:
        subject += " [partial]"

    # ── Stats from DB ─────────────────────────────────────────────────────
    stats = db.get_stats()

    # ── HTML body ─────────────────────────────────────────────────────────
    status_colors = {
        "Applied":        "#58A6FF",
        "In Progress":    "#3FB950",
        "Rejected":       "#F78166",
        "Offer Received": "#E3B341",
        "Job Opportunity":"#39D353",
        "Withdrawn":      "#8B949E",
    }

    # New items rows
    new_rows_html = ""
    if new_items:
        for item in new_items[:30]:  # cap at 30
            color = status_colors.get(item.get("status", ""), "#8B949E")
            new_rows_html += f"""
            <tr>
              <td style="padding:8px 12px;border-bottom:1px solid #30363D;">{item.get('company','—')}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #30363D;">{item.get('role','—')}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #30363D;">
                <span style="color:{color};font-weight:bold;">{item.get('status','—')}</span>
              </td>
              <td style="padding:8px 12px;border-bottom:1px solid #30363D;color:#8B949E;">{item.get('stage','—')}</td>
            </tr>"""
    else:
        new_rows_html = """<tr><td colspan="4" style="padding:16px;text-align:center;color:#8B949E;">
            No new applications or updates found today.</td></tr>"""

    # Overall stats rows
    stat_items = [
        ("Total Applications", stats.get("total", 0),          "#E6EDF3"),
        ("Applied",            stats.get("Applied", 0),         "#58A6FF"),
        ("In Progress",        stats.get("In Progress", 0),     "#3FB950"),
        ("Rejected",           stats.get("Rejected", 0),        "#F78166"),
        ("Offers",             stats.get("Offer Received", 0),  "#E3B341"),
        ("Opportunities",      stats.get("Job Opportunity", 0), "#39D353"),
    ]
    stats_rows_html = "".join(f"""
        <tr>
          <td style="padding:7px 12px;color:#8B949E;">{label}</td>
          <td style="padding:7px 12px;text-align:right;font-weight:bold;color:{color};">{count}</td>
        </tr>""" for label, count, color in stat_items)

    error_section = ""
    if errors:
        error_section = f"""
        <div style="background:#1C1018;border:1px solid #F78166;border-radius:6px;padding:12px;margin-top:16px;">
          <p style="color:#F78166;font-weight:bold;margin:0 0 6px;">⚠ Scan errors:</p>
          {''.join(f'<p style="color:#8B949E;margin:2px 0;">• {e}</p>' for e in errors)}
        </div>"""

    stopped_banner = ""
    if stopped:
        stopped_banner = """
        <div style="background:#1C1810;border:1px solid #E3B341;border-radius:6px;padding:10px;margin-bottom:12px;">
          <p style="color:#E3B341;margin:0;">⏹ Scan was stopped early — results are partial.</p>
        </div>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0D1117;font-family:'Segoe UI',Arial,sans-serif;">
  <div style="max-width:600px;margin:32px auto;background:#161B22;border-radius:10px;overflow:hidden;border:1px solid #30363D;">

    <!-- Header -->
    <div style="background:#1C2128;padding:24px 28px;border-bottom:1px solid #30363D;">
      <p style="margin:0;font-size:22px;font-weight:bold;color:#E6EDF3;">📊 JobTracker Daily Report</p>
      <p style="margin:4px 0 0;color:#8B949E;font-size:13px;">{ts}</p>
    </div>

    <div style="padding:24px 28px;">
      {stopped_banner}

      <!-- Summary chips -->
      <div style="display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap;">
        <div style="background:#1C2128;border-radius:8px;padding:12px 20px;flex:1;min-width:120px;">
          <p style="margin:0;font-size:28px;font-weight:bold;color:#58A6FF;">{new_apps}</p>
          <p style="margin:4px 0 0;color:#8B949E;font-size:12px;">NEW TODAY</p>
        </div>
        <div style="background:#1C2128;border-radius:8px;padding:12px 20px;flex:1;min-width:120px;">
          <p style="margin:0;font-size:28px;font-weight:bold;color:#3FB950;">{updates}</p>
          <p style="margin:4px 0 0;color:#8B949E;font-size:12px;">UPDATES</p>
        </div>
        <div style="background:#1C2128;border-radius:8px;padding:12px 20px;flex:1;min-width:120px;">
          <p style="margin:0;font-size:28px;font-weight:bold;color:#E6EDF3;">{stats.get('total',0)}</p>
          <p style="margin:4px 0 0;color:#8B949E;font-size:12px;">TOTAL TRACKED</p>
        </div>
      </div>

      <!-- New / updated items -->
      <p style="font-weight:bold;color:#E6EDF3;margin-bottom:10px;">Today's Activity</p>
      <table style="width:100%;border-collapse:collapse;background:#1C2128;border-radius:6px;overflow:hidden;font-size:13px;">
        <thead>
          <tr style="background:#21262D;">
            <th style="padding:9px 12px;text-align:left;color:#8B949E;font-weight:600;">Company</th>
            <th style="padding:9px 12px;text-align:left;color:#8B949E;font-weight:600;">Role</th>
            <th style="padding:9px 12px;text-align:left;color:#8B949E;font-weight:600;">Status</th>
            <th style="padding:9px 12px;text-align:left;color:#8B949E;font-weight:600;">Stage</th>
          </tr>
        </thead>
        <tbody>{new_rows_html}</tbody>
      </table>

      <!-- Overall stats -->
      <p style="font-weight:bold;color:#E6EDF3;margin:24px 0 10px;">Overall Stats</p>
      <table style="width:100%;border-collapse:collapse;background:#1C2128;border-radius:6px;overflow:hidden;font-size:13px;">
        <tbody>{stats_rows_html}</tbody>
      </table>

      {error_section}
    </div>

    <!-- Footer -->
    <div style="background:#1C2128;padding:14px 28px;border-top:1px solid #30363D;">
      <p style="margin:0;color:#484F58;font-size:11px;">Sent by JobTracker · running on your machine</p>
    </div>
  </div>
</body>
</html>"""

    # ── Plain text fallback ───────────────────────────────────────────────
    text_lines = [
        f"JobTracker Daily Report — {ts}",
        "=" * 45,
        f"New today:  {new_apps}",
        f"Updates:    {updates}",
        f"Total tracked: {stats.get('total', 0)}",
        "",
    ]
    if stopped:
        text_lines.append("⚠ Scan was stopped early — results are partial.\n")
    if new_items:
        text_lines.append("Today's activity:")
        for item in new_items[:30]:
            text_lines.append(
                f"  • {item.get('company','?')} | {item.get('role','?')} "
                f"| {item.get('status','?')} | {item.get('stage','?')}"
            )
        text_lines.append("")
    text_lines.append("Overall:")
    for label, count, _ in stat_items:
        text_lines.append(f"  {label}: {count}")
    if errors:
        text_lines.append("\nErrors:")
        for e in errors:
            text_lines.append(f"  • {e}")

    return subject, html, "\n".join(text_lines)


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN SCAN + NOTIFY FUNCTION  (called by app.py scheduler AND CLI)
# ──────────────────────────────────────────────────────────────────────────────

def run_daily_scan(days_back: int = 1, send_email: bool = True,
                   progress_cb=None, stop_flag=None) -> dict:
    """
    Perform a headless scan of all configured accounts and optionally send
    an SMTP notification email.

    Returns a dict with scan_results (same shape as build_email expects).
    """
    creds    = db.get_setting("credentials_path", "").strip()
    raw_accts = db.get_setting("gmail_accounts", "").strip()
    accounts  = [a.strip() for a in raw_accts.split("\n") if a.strip()]

    results = {
        "new_apps":  0,
        "updates":   0,
        "accounts_scanned": 0,
        "errors":    [],
        "new_items": [],
        "timestamp": datetime.now().strftime("%d %b %Y %H:%M"),
        "stopped":   False,
    }

    if not creds or not os.path.exists(creds):
        results["errors"].append("credentials.json not found — configure path in Settings.")
        _maybe_send(results, send_email)
        return results

    if not accounts:
        results["errors"].append("No Gmail accounts configured in Settings.")
        _maybe_send(results, send_email)
        return results

    try:
        import gmail_scanner
    except ImportError as e:
        results["errors"].append(f"gmail_scanner import failed: {e}")
        _maybe_send(results, send_email)
        return results

    # Snapshot jobs before scan to find what's new/changed
    jobs_before = {j["id"]: j for j in db.get_all_jobs()}

    for acct in accounts:
        if stop_flag and stop_flag():
            results["stopped"] = True
            break
        try:
            if progress_cb:
                progress_cb(f"🔍 Auto-scanning {acct}…")
            n, u = gmail_scanner.scan_account(
                acct, creds,
                days_back=days_back,
                progress_callback=progress_cb,
                scan_mode="applied",
                scan_filter="all",
                stop_flag=stop_flag,
            )
            results["new_apps"]  += n
            results["updates"]   += u
            results["accounts_scanned"] += 1
        except Exception as e:
            results["errors"].append(f"{acct}: {e}")

    # Find what's actually new or changed since scan
    jobs_after = db.get_all_jobs()
    for job in jobs_after:
        if job["id"] not in jobs_before:
            results["new_items"].append({
                "company": job.get("company", "?"),
                "role":    job.get("role", "?"),
                "status":  job.get("status", "?"),
                "stage":   job.get("stage", "?"),
            })
        elif (job.get("status") != jobs_before[job["id"]].get("status") or
              job.get("stage")  != jobs_before[job["id"]].get("stage")):
            results["new_items"].append({
                "company": job.get("company", "?"),
                "role":    job.get("role", "?"),
                "status":  job.get("status", "?"),
                "stage":   job.get("stage", "?"),
            })

    if progress_cb:
        progress_cb(f"✅ Auto-scan done — {results['new_apps']} new, {results['updates']} updates")

    _maybe_send(results, send_email, progress_cb)
    return results


def _maybe_send(results: dict, send_email: bool, progress_cb=None):
    if not send_email:
        return
    smtp_to = db.get_setting("smtp_to", "").strip()
    if not smtp_to:
        return  # silently skip if not configured
    subject, html, text = build_email(results)
    ok, msg = send_notification_email(subject, html, text)
    if progress_cb:
        progress_cb(f"{'📧' if ok else '⚠'} Email: {msg}")
    if not ok:
        print(f"[daily_scan] Email failed: {msg}")


# ──────────────────────────────────────────────────────────────────────────────
#  CLI ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="JobTracker headless daily scan")
    parser.add_argument("--days",       type=int, default=1,
                        help="How many days back to scan (default: 1)")
    parser.add_argument("--no-email",   action="store_true",
                        help="Run scan but don't send notification email")
    parser.add_argument("--test-email", action="store_true",
                        help="Send a test email without scanning")
    args = parser.parse_args()

    if args.test_email:
        print("Sending test email…")
        results = {
            "new_apps": 3, "updates": 1, "errors": [],
            "stopped": False,
            "new_items": [
                {"company": "Google",  "role": "SWE Intern",  "status": "Applied",  "stage": "Applied - Waiting"},
                {"company": "Stripe",  "role": "Backend Eng", "status": "Rejected", "stage": "Rejected"},
                {"company": "Shopify", "role": "Full Stack",  "status": "In Progress", "stage": "OA Received"},
            ],
            "timestamp": datetime.now().strftime("%d %b %Y %H:%M"),
        }
        subject, html, text = build_email(results)
        ok, msg = send_notification_email(subject, html, text)
        print(f"{'✅' if ok else '❌'} {msg}")
        return

    def cb(msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    print(f"JobTracker daily scan — {datetime.now().strftime('%d %b %Y %H:%M')}")
    results = run_daily_scan(
        days_back=args.days,
        send_email=not args.no_email,
        progress_cb=cb,
    )
    print(f"\nDone — {results['new_apps']} new, {results['updates']} updates")
    if results["errors"]:
        print("Errors:")
        for e in results["errors"]:
            print(f"  • {e}")


if __name__ == "__main__":
    main()