@echo off
setlocal EnableExtensions
title ThorGor v61 - Check Remote HoN Assets

echo This read-only check compares the remote HoN data with the working dev PC.
echo The two large archives may take a minute to hash.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0CHECK_REMOTE_ASSETS.ps1"
set "CHECK_RESULT=%ERRORLEVEL%"

echo.
if "%CHECK_RESULT%"=="0" (
  echo Asset check passed.
) else (
  echo Asset check found a difference. Send REMOTE_ASSET_CHECK.txt back to Codex.
)
pause
exit /b %CHECK_RESULT%
