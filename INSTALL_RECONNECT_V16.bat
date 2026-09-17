@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0work\install_reconnect_v16.ps1"
if errorlevel 1 (
  echo Reconnect build installation failed. See work\install_reconnect_v16.log.
  pause
  exit /b 1
)
echo Reconnect build v16 installed, verified, and started.
pause
