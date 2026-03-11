@echo off
setlocal

:: ── Move to the folder where this .bat lives ──────────────────────────────
cd /d "%~dp0"

echo ================================================
echo  JobTracker - Installation Script
echo ================================================
echo  Running from: %CD%
echo.

:: ── Check Python ──────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Please install Python 3.9+ from https://python.org
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
python --version

echo.
echo [1/5] Installing required Python packages...
echo ------------------------------------------------
python -m pip install --upgrade pip
python -m pip install ^
    google-auth ^
    google-auth-oauthlib ^
    google-auth-httplib2 ^
    google-api-python-client ^
    customtkinter ^
    pillow ^
    schedule ^
    pyinstaller

if errorlevel 1 (
    echo.
    echo WARNING: Some packages may have failed. Check output above.
)

echo.
echo [2/5] Creating data directory...
echo ------------------------------------------------
if not exist "%~dp0data" (
    mkdir "%~dp0data"
    echo   Created: %~dp0data
) else (
    echo   Already exists: %~dp0data
)

echo.
echo [3/5] Testing database setup...
echo ------------------------------------------------
python "%~dp0database.py"
if errorlevel 1 (
    echo   WARNING: Database test had issues - check above.
) else (
    echo   Database OK
)

echo.
echo [4/5] Checking all required files are present...
echo ------------------------------------------------
set MISSING=0
for %%f in (app.py gmail_scanner.py database.py daily_scan.py scheduler_setup.py) do (
    if not exist "%~dp0%%f" (
        echo   MISSING: %%f
        set MISSING=1
    ) else (
        echo   OK: %%f
    )
)
if "%MISSING%"=="1" (
    echo.
    echo   WARNING: Some files are missing. Make sure all .py files are in the same folder.
)

echo.
echo [5/5] Done!
echo ================================================
echo  To run the app, double-click:
echo    "Run_JobTracker.bat"
echo.
echo  Daily email notifications setup (optional):
echo    1. Open the app ^> Settings
echo    2. Fill in SMTP email settings
echo    3. Click "Send Test Email" to verify
echo    4. Click "Setup Daily Task" to schedule
echo       (or run: python scheduler_setup.py --install --time 08:00)
echo.
echo  To build a standalone .exe:
echo    build_exe.bat
echo ================================================
echo.
pause