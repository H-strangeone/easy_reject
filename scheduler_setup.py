"""
scheduler_setup.py  —  JobTracker Windows Task Scheduler helper
────────────────────────────────────────────────────────────────
Creates a Windows Task Scheduler task that runs daily_scan.py
every day at the time configured in Settings.

Run once:
    python scheduler_setup.py --install
    python scheduler_setup.py --remove
    python scheduler_setup.py --status
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime

TASK_NAME = "JobTrackerDailyScan"


def get_app_dir():
    return os.path.dirname(os.path.abspath(__file__))


def get_python_exe():
    return sys.executable


def install_task(run_time: str = "08:00"):
    """Create the scheduled task. run_time format: HH:MM"""
    app_dir    = get_app_dir()
    python_exe = get_python_exe()
    script     = os.path.join(app_dir, "daily_scan.py")

    if not os.path.exists(script):
        print(f"❌ daily_scan.py not found at: {script}")
        return False

    # schtasks command
    cmd = [
        "schtasks", "/create",
        "/tn",  TASK_NAME,
        "/tr",  f'"{python_exe}" "{script}"',
        "/sc",  "daily",
        "/st",  run_time,
        "/f",              # overwrite if exists
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
        if result.returncode == 0:
            print(f"✅ Task '{TASK_NAME}' created — runs daily at {run_time}")
            print(f"   Python: {python_exe}")
            print(f"   Script: {script}")
            return True
        else:
            print(f"❌ Failed to create task:\n{result.stderr or result.stdout}")
            return False
    except FileNotFoundError:
        print("❌ schtasks not found — are you on Windows?")
        return False


def remove_task():
    try:
        result = subprocess.run(
            ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"✅ Task '{TASK_NAME}' removed.")
        else:
            print(f"⚠ {result.stderr or result.stdout}")
    except FileNotFoundError:
        print("❌ schtasks not found — are you on Windows?")


def task_status():
    try:
        result = subprocess.run(
            ["schtasks", "/query", "/tn", TASK_NAME, "/fo", "LIST", "/v"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"Task '{TASK_NAME}' not found.")
    except FileNotFoundError:
        print("❌ schtasks not found — are you on Windows?")


def run_now():
    """Trigger the task immediately."""
    try:
        result = subprocess.run(
            ["schtasks", "/run", "/tn", TASK_NAME],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"✅ Task '{TASK_NAME}' triggered.")
        else:
            print(f"⚠ {result.stderr or result.stdout}")
    except FileNotFoundError:
        print("❌ schtasks not found — are you on Windows?")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JobTracker Task Scheduler setup")
    parser.add_argument("--install", action="store_true", help="Install scheduled task")
    parser.add_argument("--remove",  action="store_true", help="Remove scheduled task")
    parser.add_argument("--status",  action="store_true", help="Show task status")
    parser.add_argument("--run-now", action="store_true", help="Run task immediately")
    parser.add_argument("--time",    default="08:00",
                        help="Run time in HH:MM 24h format (default: 08:00)")
    args = parser.parse_args()

    if args.install:
        install_task(args.time)
    elif args.remove:
        remove_task()
    elif args.status:
        task_status()
    elif args.run_now:
        run_now()
    else:
        parser.print_help()