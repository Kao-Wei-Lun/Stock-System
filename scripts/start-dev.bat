@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"

if not exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
    echo [ERROR] Run scripts\setup.bat first.
    exit /b 1
)
if not exist "%PROJECT_ROOT%\frontend\node_modules" (
    echo [ERROR] Frontend dependencies are missing. Run scripts\setup.bat first.
    exit /b 1
)

"%PROJECT_ROOT%\venv\Scripts\python.exe" -X utf8 "%PROJECT_ROOT%\backend\check_runtime_environment.py"
if errorlevel 1 (
    echo [ERROR] Development services were not started because runtime security validation failed.
    exit /b 1
)

start "QuantVision Backend Dev" "%SystemRoot%\System32\cmd.exe" /k call "%PROJECT_ROOT%\scripts\start.bat" backend
start "QuantVision Frontend Dev" /D "%PROJECT_ROOT%\frontend" "%SystemRoot%\System32\cmd.exe" /k call npm run dev -- --host 127.0.0.1 --port 5173
echo [INFO] Development UI: http://localhost:5173
exit /b 0
