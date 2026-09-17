@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0work\install_reconnect_v19.ps1"
if errorlevel 1 pause
