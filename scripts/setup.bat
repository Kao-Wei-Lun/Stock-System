@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"

python --version >nul 2>&1 || (echo [ERROR] Python 3.10+ is required. & exit /b 1)
where npm >nul 2>&1 || (echo [ERROR] Node.js 18+ is required. & exit /b 1)

if not exist "%PROJECT_ROOT%\venv\Scripts\python.exe" python -m venv "%PROJECT_ROOT%\venv"
"%PROJECT_ROOT%\venv\Scripts\python.exe" -m pip install -r "%PROJECT_ROOT%\backend\requirements.txt"
if errorlevel 1 exit /b 1
if exist "%PROJECT_ROOT%\docs\fubon_neo-2.2.8-cp37-abi3-win_amd64.whl" "%PROJECT_ROOT%\venv\Scripts\python.exe" -m pip install "%PROJECT_ROOT%\docs\fubon_neo-2.2.8-cp37-abi3-win_amd64.whl"
if errorlevel 1 exit /b 1
cd /d "%PROJECT_ROOT%\frontend"
call npm install
if errorlevel 1 exit /b 1
call "%PROJECT_ROOT%\scripts\build-frontend.bat"
