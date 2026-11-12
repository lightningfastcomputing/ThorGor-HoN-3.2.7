@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\install_reconnect_v39.ps1"
if errorlevel 1 pause
