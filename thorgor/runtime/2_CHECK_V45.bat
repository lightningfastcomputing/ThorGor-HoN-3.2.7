@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0CHECK_RUNTIME.ps1"
exit /b %ERRORLEVEL%
