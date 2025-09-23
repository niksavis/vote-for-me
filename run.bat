@echo off
echo Starting Vote For Me Application...
echo.

REM Set development mode by default (can be overridden with: set VOTE_ENV=production)
if not defined VOTE_ENV set VOTE_ENV=development

echo Environment: %VOTE_ENV%
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    echo Please install Python 3.8 or higher.
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Install/upgrade requirements
echo Installing dependencies...
pip install -r requirements.txt

REM Create data directory if it doesn't exist
if not exist "data" (
    echo Creating data directory...
    mkdir data
    mkdir data\active
    mkdir data\completed
)

REM Setup MailHog only in development environment
if /i "%VOTE_ENV%"=="development" (
    if not exist "mailhog" (
        echo Creating mailhog directory...
        mkdir mailhog
    )

    if not exist "mailhog\mailhog.exe" (
        echo MailHog not found. Downloading latest version from GitHub...
        echo This is required for email functionality in development.
        echo.
        
        REM Get the latest release URL and download MailHog
        powershell -Command "& {$latest = Invoke-RestMethod -Uri 'https://api.github.com/repos/mailhog/MailHog/releases/latest'; $asset = $latest.assets | Where-Object {$_.name -eq 'MailHog_windows_amd64.exe'}; if ($asset) { Invoke-WebRequest -Uri $asset.browser_download_url -OutFile 'mailhog\mailhog.exe'; Write-Host 'Downloaded MailHog version:' $latest.tag_name } else { Write-Host 'Windows AMD64 asset not found in latest release' }}"
        
        if not exist "mailhog\mailhog.exe" (
            echo Failed to download MailHog. Please check your internet connection.
            echo You can manually download it from: https://github.com/mailhog/MailHog/releases
            echo.
        ) else (
            echo MailHog downloaded successfully!
            echo.
        )
    )

    REM Start MailHog for email testing in development
    if exist "mailhog\mailhog.exe" (
        echo Starting MailHog email server for development...
        start /B "" "mailhog\mailhog.exe"
        timeout /t 3 >nul
        echo MailHog is running - Web interface: http://localhost:8025
        echo.
    ) else (
        echo Warning: MailHog not available. Email functionality may not work in development.
        echo.
    )
) else (
    echo Production mode: Skipping MailHog setup.
    echo Configure email settings through the application's config page.
    echo.
)

REM Start the application
echo.
if /i "%VOTE_ENV%"=="development" (
    echo ===============================================
    echo   STARTING VOTE FOR ME - DEVELOPMENT MODE
    echo ===============================================
    echo   The application will show network URLs when ready
    echo   Look for the "VOTE FOR ME" banner below
    echo   MailHog web interface: http://localhost:8025
    echo ===============================================
) else (
    echo ===============================================
    echo   STARTING VOTE FOR ME - PRODUCTION MODE
    echo ===============================================
    echo   The application will show network URLs when ready
    echo   Look for the "VOTE FOR ME" banner below
    echo   Configure email in app: http://localhost:5000/config
    echo ===============================================
)
echo.

python app.py
