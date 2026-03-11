@echo off
:: ── Always run from the folder this .bat is in ───────────────────────────
cd /d "%~dp0"
echo Starting JobTracker...
python "%~dp0app.py"
if errorlevel 1 (
    echo.
    echo App failed to start. Common fixes:
    echo  1. Run install.bat first
    echo  2. Make sure Python is installed: python.org
    echo  3. Make sure all files are present:
    echo       app.py, gmail_scanner.py, database.py,
    echo       daily_scan.py, scheduler_setup.py
    pause
)