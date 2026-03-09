@echo off
echo ================================================
echo  JobTracker - Build Windows .exe
echo ================================================
echo.

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
    --hidden-import "google.auth" ^
    --hidden-import "google.auth.transport.requests" ^
    --hidden-import "google_auth_oauthlib.flow" ^
    --hidden-import "googleapiclient.discovery" ^
    --hidden-import "googleapiclient.errors" ^
    --hidden-import "customtkinter" ^
    --hidden-import "PIL" ^
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
echo  NOTE: On first run, copy credentials.json
echo  to the same folder as JobTracker.exe
echo  and configure it in the app's Settings.
echo ================================================
pause
