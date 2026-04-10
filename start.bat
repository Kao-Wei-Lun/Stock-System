@echo off
setlocal EnableExtensions
chcp 65001 >nul

cd /d "%~dp0"

if /i "%~1"=="docker" (
    docker compose up --build
    exit /b %errorlevel%
)

call "%~dp0scripts\start.bat" %*
exit /b %errorlevel%
