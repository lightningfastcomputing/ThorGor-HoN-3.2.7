@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install_reconnect_v25.ps1"
if errorlevel 1 pause
