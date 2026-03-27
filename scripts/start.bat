@echo off
chcp 65001 >nul
title QuantVision Pro

echo ======================================
echo    QuantVision Pro starting...
echo ======================================

cd /d "%~dp0.."
set "PYTHON_CMD="
set "NODE_EXE="
set "NODE_DIR="
set "NPM_EXE="
set "BACKEND_URL=http://localhost:8001"
set "FRONTEND_URL=http://localhost:5173"
set "FRONTEND_DEV_URL=%FRONTEND_URL%"

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

where node >nul 2>&1
for /f "delims=" %%I in ('where node 2^>nul') do if not defined NODE_EXE set "NODE_EXE=%%I"

if not defined NODE_EXE if exist "%ProgramFiles%\nodejs\node.exe" set "NODE_EXE=%ProgramFiles%\nodejs\node.exe"
if not defined NODE_EXE if exist "%ProgramFiles(x86)%\nodejs\node.exe" set "NODE_EXE=%ProgramFiles(x86)%\nodejs\node.exe"

if not defined NODE_EXE (
    echo [ERROR] Node.js 18+ was not found.
    echo         Download: https://nodejs.org/
    pause
    exit /b 1
)

for %%I in ("%NODE_EXE%") do set "NODE_DIR=%%~dpI"
if defined NODE_DIR set "PATH=%NODE_DIR%;%PATH%"

for /f "delims=" %%I in ('where npm 2^>nul') do if not defined NPM_EXE set "NPM_EXE=%%I"

if not defined NPM_EXE if exist "%ProgramFiles%\nodejs\npm.cmd" set "NPM_EXE=%ProgramFiles%\nodejs\npm.cmd"
if not defined NPM_EXE if exist "%ProgramFiles(x86)%\nodejs\npm.cmd" set "NPM_EXE=%ProgramFiles(x86)%\nodejs\npm.cmd"

if not defined NPM_EXE (
    echo [ERROR] npm was not found.
    echo         Reinstall Node.js from: https://nodejs.org/
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

set "VENV_PYTHON=%CD%\venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" (
    echo [ERROR] Virtual environment Python was not found.
    pause
    exit /b 1
)

echo [INFO] Installing backend dependencies...
"%VENV_PYTHON%" -m pip install --upgrade pip -q
"%VENV_PYTHON%" -m pip install -r backend\requirements.txt -q
if errorlevel 1 (
    echo.
    echo [ERROR] Backend dependency installation failed.
    pause
    exit /b 1
)

echo [INFO] Installing frontend dependencies...
pushd frontend
call "%NPM_EXE%" install
if errorlevel 1 (
    popd
    echo.
    echo [ERROR] Frontend dependency installation failed.
    pause
    exit /b 1
)
popd

if /i "%QV_VALIDATE_ONLY%"=="1" (
    echo [INFO] Validation completed.
    exit /b 0
)

set "FRONTEND_ALREADY_RUNNING="
for /f "tokens=5" %%I in ('netstat -ano ^| findstr /R /C:":5173 .*LISTENING" 2^>nul') do if not defined FRONTEND_ALREADY_RUNNING set "FRONTEND_ALREADY_RUNNING=1"

echo.
if defined FRONTEND_ALREADY_RUNNING (
    echo [INFO] Frontend service already running.
    echo        Frontend: %FRONTEND_URL%
) else (
    echo [INFO] Starting frontend service...
    echo        Frontend: %FRONTEND_URL%
    start "QuantVision Frontend" powershell -NoExit -ExecutionPolicy Bypass -Command "$env:Path='%NODE_DIR%;' + $env:Path; Set-Location -LiteralPath '%CD%\frontend'; & '%NPM_EXE%' run dev -- --host 0.0.0.0 --port 5173"
    powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(15); while((Get-Date) -lt $deadline){ try { $r=Invoke-WebRequest -UseBasicParsing 'http://localhost:5173' -TimeoutSec 2; if($r.StatusCode -ge 200){ exit 0 } } catch {}; Start-Sleep -Milliseconds 500 }; exit 1" >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] Frontend service did not respond on %FRONTEND_URL%.
        echo           Check the "QuantVision Frontend" window for the exact error.
    )
)

timeout /t 2 /nobreak >nul

echo.
echo [INFO] Starting backend API...
echo        Backend: %BACKEND_URL%
echo        Frontend dev server: %FRONTEND_URL%
echo        API docs: %BACKEND_URL%/docs
echo.
echo [INFO] Press Ctrl+C to stop the backend.
echo        Close the "QuantVision Frontend" window to stop Vite.
echo ======================================

cd backend
"%VENV_PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload

pause
