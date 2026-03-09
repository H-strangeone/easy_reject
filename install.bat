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
echo [1/4] Installing required Python packages...
echo ------------------------------------------------
python -m pip install --upgrade pip
python -m pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client customtkinter pillow schedule pyinstaller

if errorlevel 1 (
    echo.
    echo WARNING: Some packages may have failed. Check output above.
)

echo.
echo [2/4] Creating data directory...
echo ------------------------------------------------
if not exist "%~dp0data" (
    mkdir "%~dp0data"
    echo   Created: %~dp0data
) else (
    echo   Already exists: %~dp0data
)

echo.
echo [3/4] Testing database setup...
echo ------------------------------------------------
python "%~dp0database.py"
if errorlevel 1 (
    echo   WARNING: Database test had issues - check above.
) else (
    echo   Database OK
)

echo.
echo [4/4] Done!
echo ================================================
echo  To run the app, double-click:
echo    "Run JobTracker.bat"
echo.
echo  Or in Command Prompt:
echo    python "%~dp0app.py"
echo.
echo  To build a standalone .exe:
echo    build_exe.bat
echo ================================================
echo.
pause
