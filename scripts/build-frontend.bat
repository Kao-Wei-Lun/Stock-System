@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0..\frontend"
if not exist "node_modules" (
    echo [ERROR] Frontend dependencies are missing. Run scripts\setup.bat first.
    exit /b 1
)
call npm run build
exit /b %errorlevel%
