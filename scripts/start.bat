@echo off
setlocal EnableExtensions
chcp 65001 >nul

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"
set "BACKEND_PORT=8001"
if not defined APP_BIND_HOST set "APP_BIND_HOST=127.0.0.1"
if not defined FRONTEND_BIND_HOST set "FRONTEND_BIND_HOST=127.0.0.1"
set "BACKEND_URL=http://127.0.0.1:%BACKEND_PORT%"
set "APP_URL=%BACKEND_URL%/app/"
set "VENV_PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe"

if /i "%~1"=="backend" goto backend

title QuantVision Production Launcher
if not exist "%PROJECT_ROOT%\frontend\dist\index.html" (
    echo [ERROR] Production frontend is missing.
    echo         Run scripts\build-frontend.bat first.
    exit /b 1
)
if not exist "%VENV_PYTHON%" (
    echo [ERROR] Python environment is missing.
    echo         Run scripts\setup.bat first.
    exit /b 1
)

call :stop_port %BACKEND_PORT% Backend
echo [INFO] Starting QuantVision production service...
start "QuantVision" "%SystemRoot%\System32\cmd.exe" /k call "%~f0" backend
call :wait_for_http "%BACKEND_URL%/api/ready" 60 || (
    echo [ERROR] Backend did not become ready. Check the QuantVision window.
    exit /b 1
)
call :wait_for_http "%APP_URL%" 15 || (
    echo [ERROR] Frontend did not become available: %APP_URL%
    echo         Run scripts\build-frontend.bat and restart the system.
    pause
    exit /b 1
)
echo [INFO] Backend and frontend are ready.
echo [INFO] Opening QuantVision: %APP_URL%
call :open_browser "%APP_URL%" || (
    echo [WARNING] Windows could not open the browser automatically.
    echo [WARNING] Open this URL manually: %APP_URL%
    pause
    exit /b 1
)
echo [INFO] QuantVision is ready: %APP_URL%
exit /b 0

:backend
title QuantVision
if not exist "%VENV_PYTHON%" exit /b 1
cd /d "%PROJECT_ROOT%\backend"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
"%VENV_PYTHON%" -X utf8 -m uvicorn main:app --host %APP_BIND_HOST% --port %BACKEND_PORT% --no-use-colors
exit /b %errorlevel%

:stop_port
for /f "tokens=5" %%I in ('netstat -ano ^| findstr /R /C:":%~1 .*LISTENING" 2^>nul') do taskkill /PID %%I /T /F >nul 2>&1
exit /b 0

:open_browser
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { Start-Process -FilePath '%~1' -ErrorAction Stop; exit 0 } catch { Write-Error $_.Exception.Message; exit 1 }"
exit /b %errorlevel%

:wait_for_http
setlocal
set /a "ELAPSED=0"
:wait_loop
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -Uri '%~1' -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -lt 400) { exit 0 }; exit 1 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (endlocal & exit /b 0)
if %ELAPSED% GEQ %~2 (endlocal & exit /b 1)
timeout /t 1 /nobreak >nul
set /a "ELAPSED+=1"
goto wait_loop
