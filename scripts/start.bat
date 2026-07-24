@echo off
setlocal EnableExtensions
chcp 65001 >nul

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"
set "BACKEND_PORT=8001"
if not defined FRONTEND_BIND_HOST set "FRONTEND_BIND_HOST=127.0.0.1"
set "BACKEND_URL=http://127.0.0.1:%BACKEND_PORT%"
set "APP_URL=%BACKEND_URL%/app/"
set "VENV_PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe"
set "SUPERVISOR=%PROJECT_ROOT%\backend\service_supervisor.py"
set "RUNTIME_CHECK=%PROJECT_ROOT%\backend\check_runtime_environment.py"
set "RUNTIME_DIR=%PROJECT_ROOT%\.runtime"

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Python environment is missing.
    echo         Run scripts\setup.bat first.
    exit /b 1
)
if not exist "%SUPERVISOR%" (
    echo [ERROR] Service supervisor is missing: %SUPERVISOR%
    exit /b 1
)

if /i "%~1"=="stop" goto stop
if /i "%~1"=="status" goto status

"%VENV_PYTHON%" -X utf8 "%RUNTIME_CHECK%"
if errorlevel 1 (
    echo [ERROR] QuantVision refused to start because runtime security validation failed.
    exit /b 1
)
for /f "delims=" %%H in ('""%VENV_PYTHON%" -X utf8 "%RUNTIME_CHECK%" --bind-host"') do set "APP_BIND_HOST=%%H"
if not defined APP_BIND_HOST (
    echo [ERROR] Unable to resolve the validated backend bind host.
    exit /b 1
)

if /i "%~1"=="backend" goto backend

title QuantVision Production Launcher
if not exist "%PROJECT_ROOT%\frontend\dist\index.html" (
    echo [ERROR] Production frontend is missing.
    echo         Run scripts\build-frontend.bat first.
    exit /b 1
)

"%VENV_PYTHON%" -X utf8 "%SUPERVISOR%" check --python "%VENV_PYTHON%" --working-directory "%PROJECT_ROOT%\backend" --runtime-dir "%RUNTIME_DIR%" --host "%APP_BIND_HOST%" --port %BACKEND_PORT%
set "PREFLIGHT_RESULT=%ERRORLEVEL%"
if "%PREFLIGHT_RESULT%"=="20" (
    echo [ERROR] Port %BACKEND_PORT% is occupied by an unconfirmed process.
    echo         QuantVision did not stop or replace that process.
    exit /b 1
)
if not "%PREFLIGHT_RESULT%"=="0" if not "%PREFLIGHT_RESULT%"=="10" (
    echo [ERROR] Service preflight failed with code %PREFLIGHT_RESULT%.
    exit /b 1
)
if "%PREFLIGHT_RESULT%"=="0" (
    echo [INFO] Starting supervised QuantVision production service...
    start "QuantVision Service" "%SystemRoot%\System32\cmd.exe" /k call "%~f0" backend
)
if "%PREFLIGHT_RESULT%"=="10" (
    echo [INFO] Reusing the confirmed QuantVision backend already on port %BACKEND_PORT%.
)

call :wait_for_http "%BACKEND_URL%/api/ready" 60 || (
    echo [ERROR] Backend did not become ready.
    echo         Run start.bat status and inspect log\backend.log.
    exit /b 1
)
call :wait_for_http "%APP_URL%" 15 || (
    echo [ERROR] Frontend did not become available: %APP_URL%
    echo         Run scripts\build-frontend.bat and restart the system.
    pause
    exit /b 1
)
echo [INFO] Backend and production frontend are ready.
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
title QuantVision Supervised Service
cd /d "%PROJECT_ROOT%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "QUANTVISION_RUNTIME_PROFILE=production"
"%VENV_PYTHON%" -X utf8 "%SUPERVISOR%" run --python "%VENV_PYTHON%" --working-directory "%PROJECT_ROOT%\backend" --runtime-dir "%RUNTIME_DIR%" --host "%APP_BIND_HOST%" --port %BACKEND_PORT%
set "SERVICE_RESULT=%ERRORLEVEL%"
if "%SERVICE_RESULT%"=="70" (
    echo [ERROR] Restart breaker is open after repeated backend crashes.
    echo         Inspect log\backend.log and run start.bat status before restarting.
)
exit /b %SERVICE_RESULT%

:stop
if not defined APP_BIND_HOST set "APP_BIND_HOST=127.0.0.1"
echo [INFO] Requesting a planned QuantVision shutdown...
"%VENV_PYTHON%" -X utf8 "%SUPERVISOR%" stop --python "%VENV_PYTHON%" --working-directory "%PROJECT_ROOT%\backend" --runtime-dir "%RUNTIME_DIR%" --host "%APP_BIND_HOST%" --port %BACKEND_PORT%
exit /b %ERRORLEVEL%

:status
if not defined APP_BIND_HOST set "APP_BIND_HOST=127.0.0.1"
"%VENV_PYTHON%" -X utf8 "%SUPERVISOR%" status --python "%VENV_PYTHON%" --working-directory "%PROJECT_ROOT%\backend" --runtime-dir "%RUNTIME_DIR%" --host "%APP_BIND_HOST%" --port %BACKEND_PORT%
exit /b %ERRORLEVEL%

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
