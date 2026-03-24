@echo off
chcp 65001 >nul
title QuantVision Pro

echo ======================================
echo    QuantVision Pro starting...
echo ======================================

cd /d "%~dp0.."
set "PYTHON_CMD="

python --version >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
    py -3.13 --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3.13"
)

if not defined PYTHON_CMD (
    py --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py"
)

if not defined PYTHON_CMD (
    echo [ERROR] Python 3.10+ was not found.
    echo         Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist "venv" (
    echo [INFO] Creating virtual environment...
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [INFO] Installing dependencies...
python -m pip install --upgrade pip -q
python -m pip install -r backend\requirements.txt -q
if errorlevel 1 (
    echo.
    echo [ERROR] Dependency installation failed.
    echo         Retry with: python -m pip install -r backend\requirements.txt
    pause
    exit /b 1
)

echo.
echo [INFO] Starting backend API...
echo        Backend: http://localhost:8001
echo        Frontend: http://localhost:8001/app
echo        API docs: http://localhost:8001/docs
echo.
echo [INFO] First startup will download Yahoo Finance history data.
echo        Press Ctrl+C to stop the server.
echo ======================================

cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload

pause
