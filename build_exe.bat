@echo off
echo ================================================
echo  JobTracker - Build Windows .exe
echo ================================================
echo.

cd /d "%~dp0"

:: Check pyinstaller
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo Building executable...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "JobTracker" ^
    --add-data "database.py;." ^
    --add-data "gmail_scanner.py;." ^
    --add-data "daily_scan.py;." ^
    --add-data "scheduler_setup.py;." ^
    --add-data "calendar_helper.py;." ^
    --hidden-import "google.auth" ^
    --hidden-import "google.auth.transport.requests" ^
    --hidden-import "google_auth_oauthlib.flow" ^
    --hidden-import "googleapiclient.discovery" ^
    --hidden-import "googleapiclient.errors" ^
    --hidden-import "customtkinter" ^
    --hidden-import "PIL" ^
    --hidden-import "smtplib" ^
    --hidden-import "ssl" ^
    --hidden-import "email.mime.text" ^
    --hidden-import "email.mime.multipart" ^
    --collect-all "customtkinter" ^
    app.py

if errorlevel 1 (
    echo.
    echo Build FAILED. Check errors above.
    pause
    exit /b 1
)

echo.
echo ================================================
echo  Build successful!
echo  Your .exe is at: dist\JobTracker.exe
echo.
echo  IMPORTANT - copy these to the same folder as JobTracker.exe:
echo    - credentials.json  (your Google OAuth file)
echo.
echo  NOTE: The "Setup Daily Task" button in Settings will
echo  register a Windows scheduled task pointing to daily_scan.py
echo  in the original source folder (not the .exe dist folder).
echo  For the .exe build, set up the task manually:
echo    python scheduler_setup.py --install --time 08:00
echo  from the source folder, or use Task Scheduler directly.
echo ================================================
pause