@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ThorGor HoN 3.2.7.1 - v61 Complete Registry Guard
color 0A

set "HON_HOME=C:\Program Files (x86)\Heroes of Newerth"
if not exist "%HON_HOME%\hon.exe" (
  echo Required HoN executable was not found:
  echo   %HON_HOME%\hon.exe
  echo Install HoN 3.2.7.1 in the canonical Program Files folder, then retry.
  goto :failed
)

echo ============================================================
echo ThorGor HoN 3.2.7.1 - V61 COMPLETE REGISTRY GUARD
echo ============================================================
echo.
echo Server networking retains the v57 two-client admission fix.
echo Both clients receive primary and fallback registry guards.
echo Manager/slave control and real UDP target remain localhost.
echo HoN executables: %HON_HOME%
echo.

set "LAN_IP=%~1"
if defined LAN_IP (
  echo Requested LAN address: %LAN_IP%
) else (
  echo No LAN address supplied. Dashboard will auto-detect it.
)
echo.

echo Ensuring Windows Firewall allows ThorGor LAN ports...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ENSURE_V49_LAN_FIREWALL.ps1"
if errorlevel 1 goto :failed

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0CLEANUP_OLD_TESTS.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PATCH_K2_V57.ps1" -HonHome "%HON_HOME%"
if errorlevel 1 goto :failed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PATCH_CGAME_V61.ps1" -HonHome "%HON_HOME%"
if errorlevel 1 goto :failed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RESET_V43.ps1"
if errorlevel 1 goto :failed

rem Preserve the proven milestone's local test accounts and launch behavior.
python "%~dp0thorgor_hon_sandboxed_masterserver_v39.py" --password-chain pre-md5 --add-account pwnrbwnr pwnrbwnr --nickname pwnrbwnr
if errorlevel 1 goto :failed
python "%~dp0thorgor_hon_sandboxed_masterserver_v39.py" --password-chain pre-md5 --add-account player player --nickname player
if errorlevel 1 goto :failed

set "PYTHONW=pythonw.exe"
where pythonw.exe >nul 2>nul
if errorlevel 1 set "PYTHONW=python.exe"

if defined LAN_IP (
  start "ThorGor HoN v61 Complete Registry Guard" /D "%~dp0" "%PYTHONW%" "%~dp0hon_v49_dashboard.py" "%LAN_IP%"
) else (
  start "ThorGor HoN v61 Complete Registry Guard" /D "%~dp0" "%PYTHONW%" "%~dp0hon_v49_dashboard.py"
)
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo LAN startup aborted. Read the error above.
pause
exit /b 5
