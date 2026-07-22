@echo off
setlocal EnableExtensions
chcp 65001 >nul

for %%I in ("%~f0") do set "SCRIPT_PATH=%%~fI"
cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"
set "BACKEND_PORT=8001"
set "FRONTEND_PORT=5173"
if not defined APP_BIND_HOST set "APP_BIND_HOST=127.0.0.1"
if not defined FRONTEND_BIND_HOST set "FRONTEND_BIND_HOST=127.0.0.1"
set "BACKEND_URL=http://localhost:%BACKEND_PORT%"
set "FRONTEND_URL=http://localhost:%FRONTEND_PORT%"
set "FRONTEND_DEV_URL=%FRONTEND_URL%"
set "CMD_EXE=%SystemRoot%\System32\cmd.exe"
set "PYTHON_CMD="
set "NODE_EXE="
set "NODE_DIR="
set "NPM_EXE="
set "VENV_PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe"

if /i "%~1"=="frontend" goto frontend
if /i "%~1"=="backend" goto backend

title QuantVision Service Launcher

net session >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath $env:ComSpec -ArgumentList '/c call ""%SCRIPT_PATH%""' -Verb RunAs"
    exit /b
)

echo ======================================
echo    QuantVision Pro starting...
echo ======================================

call :stop_port %FRONTEND_PORT% Frontend
call :stop_port %BACKEND_PORT% Backend
call :resolve_python || exit /b 1
call :resolve_node || exit /b 1
call :ensure_venv || exit /b 1

echo.
echo [INFO] Launching backend service in a new admin cmd window...
start "QuantVision Backend" "%CMD_EXE%" /k call "%SCRIPT_PATH%" backend

echo [INFO] Waiting for backend health check...
call :wait_for_http "%BACKEND_URL%/api/ready" "Backend API" 90 || (
    echo [ERROR] Backend did not become ready in time.
    echo         Please check the "QuantVision Backend" window for details.
    exit /b 1
)

echo [INFO] Launching frontend service in a new admin cmd window...
start "QuantVision Frontend" "%CMD_EXE%" /k call "%SCRIPT_PATH%" frontend

echo.
echo [INFO] Frontend window: QuantVision Frontend
echo        URL: %FRONTEND_URL%
echo [INFO] Backend window: QuantVision Backend
echo        URL: %BACKEND_URL%
echo        Docs: %BACKEND_URL%/docs
echo.
echo [INFO] Both services are running in separate elevated cmd windows.
echo        Close each cmd window to stop its service.
exit /b 0

:frontend
title QuantVision Frontend
call :resolve_node || exit /b 1
if defined NODE_DIR set "PATH=%NODE_DIR%;%PATH%"

echo ======================================
echo    QuantVision Frontend
echo ======================================
cd /d "%PROJECT_ROOT%\frontend"

echo [INFO] Installing frontend dependencies...
call "%NPM_EXE%" install
if errorlevel 1 (
    echo [ERROR] Failed to install frontend dependencies.
    exit /b 1
)

echo [INFO] Starting frontend dev server on port %FRONTEND_PORT%...
call "%NPM_EXE%" run dev -- --host %FRONTEND_BIND_HOST% --port %FRONTEND_PORT%
exit /b %errorlevel%

:backend
title QuantVision Backend
call :resolve_python || exit /b 1
call :ensure_venv || exit /b 1

echo ======================================
echo    QuantVision Backend
echo ======================================
cd /d "%PROJECT_ROOT%"
call "%PROJECT_ROOT%\venv\Scripts\activate.bat"
set "FRONTEND_DEV_URL=%FRONTEND_DEV_URL%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo [INFO] Installing backend dependencies...
"%VENV_PYTHON%" -m pip install --upgrade pip -q
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    exit /b 1
)

"%VENV_PYTHON%" -m pip install -r "%PROJECT_ROOT%\backend\requirements.txt" -q
if errorlevel 1 (
    echo [ERROR] Failed to install backend dependencies.
    exit /b 1
)

if exist "%PROJECT_ROOT%\docs\fubon_neo-2.2.8-cp37-abi3-win_amd64.whl" (
    echo [INFO] Installing local Fubon Neo SDK wheel...
    "%VENV_PYTHON%" -m pip install "%PROJECT_ROOT%\docs\fubon_neo-2.2.8-cp37-abi3-win_amd64.whl" -q
    if errorlevel 1 (
        echo [ERROR] Failed to install Fubon Neo SDK wheel.
        exit /b 1
    )
)

echo [INFO] Starting backend API on port %BACKEND_PORT%...
cd /d "%PROJECT_ROOT%\backend"
"%VENV_PYTHON%" -X utf8 -m uvicorn main:app --host %APP_BIND_HOST% --port %BACKEND_PORT% --no-use-colors
exit /b %errorlevel%

:resolve_python
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
    exit /b 1
)
exit /b 0

:resolve_node
set "NODE_EXE="
set "NODE_DIR="
set "NPM_EXE="

for /f "delims=" %%I in ('where node 2^>nul') do if not defined NODE_EXE set "NODE_EXE=%%I"
if not defined NODE_EXE if exist "%ProgramFiles%\nodejs\node.exe" set "NODE_EXE=%ProgramFiles%\nodejs\node.exe"
if not defined NODE_EXE if exist "%ProgramFiles(x86)%\nodejs\node.exe" set "NODE_EXE=%ProgramFiles(x86)%\nodejs\node.exe"

if not defined NODE_EXE (
    echo [ERROR] Node.js 18+ was not found.
    echo         Download: https://nodejs.org/
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
    exit /b 1
)
exit /b 0

:ensure_venv
if not exist "%PROJECT_ROOT%\venv" (
    echo [INFO] Creating virtual environment...
    %PYTHON_CMD% -m venv "%PROJECT_ROOT%\venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        exit /b 1
    )
)

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Virtual environment Python was not found.
    exit /b 1
)
exit /b 0

:stop_port
setlocal
set "PORT=%~1"
set "LABEL=%~2"
set "FOUND="
for /f "tokens=5" %%I in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING" 2^>nul') do (
    if not defined FOUND (
        echo [INFO] Stopping existing %LABEL% service on port %PORT%...
        set "FOUND=1"
    )
    taskkill /PID %%I /T /F >nul 2>&1
)
endlocal
exit /b 0

:wait_for_http
setlocal
set "TARGET_URL=%~1"
set "LABEL=%~2"
set "MAX_WAIT=%~3"
if not defined MAX_WAIT set "MAX_WAIT=60"
set /a "ELAPSED=0"

:wait_for_http_loop
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { $response = Invoke-WebRequest -Uri '%TARGET_URL%' -UseBasicParsing -TimeoutSec 3; if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    endlocal
    exit /b 0
)

if %ELAPSED% GEQ %MAX_WAIT% (
    endlocal
    exit /b 1
)

timeout /t 1 /nobreak >nul
set /a "ELAPSED+=1"
goto wait_for_http_loop
