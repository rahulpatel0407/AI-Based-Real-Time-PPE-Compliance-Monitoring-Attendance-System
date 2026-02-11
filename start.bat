@echo off
REM IOCL Refinery Safety System - Quick Start Guide (Windows)

echo.
echo ==========================================
echo IOCL Refinery Safety ^& Attendance System
echo ==========================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo X Python is not installed. Please install Python 3.8 or higher.
    exit /b 1
)

echo + Python detected
echo.

REM Install dependencies
echo [*] Installing dependencies...
pip install -r requirements.txt
echo + Dependencies installed
echo.

REM Create database
echo [*] Initializing database...
python -c "from database import init_db; init_db(); print('+ Database initialized')"
echo.

echo ==========================================
echo Running Services
echo ==========================================
echo.

REM Start Flask backend
echo [*] Starting Flask Backend (Port 5000)...
start "IOCL Backend" cmd /k python backend.py
timeout /t 2 /nobreak

echo.
echo ==========================================
echo + System is Ready!
echo ==========================================
echo.
echo [*] Access the Dashboard:
echo     -> http://localhost:5000
echo.
echo [*] Streamlit App:
echo     -> streamlit run app1.py
echo.
echo [*] Backend API Docs:
echo     -> Check IOCL_DASHBOARD_README.md
echo.
echo [*] Press Ctrl+C in the backend window to stop
echo.

pause
