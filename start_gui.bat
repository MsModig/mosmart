@echo off
REM MoSMART Desktop GUI Startup Script for Windows

echo.
echo ==========================================
echo   MoSMART Desktop GUI Launcher
echo ==========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed
    pause
    exit /b 1
)

REM Check if PyQt5 is installed
python -c "import PyQt5" >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] PyQt5 is not installed. Installing...
    pip install PyQt5 PyQtChart requests
)

REM Check if backend is running
curl -s http://localhost:5000/api/devices >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Backend server is not running
    echo.
    set /p START_BACKEND="Start backend server now? (Y/N): "
    
    if /i "%START_BACKEND%"=="Y" (
        echo Starting backend server...
        start /min python web_monitor.py --port 5000
        timeout /t 3 /nobreak >nul
        echo [OK] Backend server started
    ) else (
        echo [ERROR] Backend server is required to run the GUI
        pause
        exit /b 1
    )
) else (
    echo [OK] Backend server is already running
)

echo.
echo Starting GUI...
python gui_monitor.py

echo.
echo Goodbye!
pause
