@echo off
rem Double-click to open the spending dashboard. The desktop shortcut runs this.
rem This window has to stay open while you use the dashboard: closing it stops it.
title Spending dashboard - close this window to stop it
cd /d "%~dp0"

if not exist ".venv\Scripts\chase-import.exe" (
    echo Can't find the app in this folder: %~dp0
    echo It needs to be installed first. See "One-time setup" in README.md.
    pause
    exit /b 1
)

echo Opening your spending dashboard in the browser...
echo Keep this window open while you use it. Close it when you're done.
echo.
".venv\Scripts\chase-import.exe" dashboard

rem Only reached if the dashboard stopped with an error: keep the message on screen.
if errorlevel 1 pause
