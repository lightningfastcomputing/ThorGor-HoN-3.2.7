@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ThorGor v75 server-side joined-client hero-state fix
echo - Reconciles only state blocks 3 through 8.
echo - Uses K2's guarded queue so snapshot state sequences stay synchronized.
echo - The v74 UDP packet injection is disabled.
echo.

if not defined HON_HOME (
    if exist "C:\intelprop\Heroes of Newerth\hon.exe" (
        set "HON_HOME=C:\intelprop\Heroes of Newerth"
    ) else (
        set "HON_HOME=C:\Program Files (x86)\Heroes of Newerth"
    )
)
set "THORGOR_HON_HOME=%HON_HOME%"

if not exist "%HON_HOME%\hon.exe" (
    echo ERROR: hon.exe was not found in:
    echo   %HON_HOME%
    pause
    exit /b 2
)

echo Installing and verifying K2 v75 plus cgame v61 in:
echo   %HON_HOME%
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_V75_PATCHES.ps1" -HonHome "%HON_HOME%"
if errorlevel 1 (
    echo ERROR: v75 DLL installation failed. Do not start a client.
    pause
    exit /b 3
)

echo Resetting volatile ThorGor runtime state for a clean test...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RESET_V42.ps1"
if errorlevel 1 (
    echo ERROR: ThorGor runtime-state reset failed. Do not continue this run.
    pause
    exit /b 4
)
for %%F in ("work\native_matchid_bridge_v47.log" "work\native_matchid_bridge_v47_state.json" "work\hon_udp_shim_public_list.log" "work\hon_udp_shim_hot_stdout.log" "work\hon_udp_shim_hot_stderr.log" "work\v43_run_id.txt") do (
    if exist "%%~F" del /q "%%~F" >nul 2>nul
)
for %%D in ("thorgor_server_v39_captures" "thorgor_srp_v39_captures" "chat-server\thorgor_chat_v13_captures" "chat-server\thorgor_chat_v13_host_captures" "dashboard_logs" "work\route_traces") do (
    if exist "%%~D" del /q "%%~D\*" >nul 2>nul
)
echo Clean state prepared.
echo.

set "PYEXE="
for /f "delims=" %%P in ('where python.exe 2^>nul') do (
    if not defined PYEXE set "PYEXE=%%P"
)
if not defined PYEXE (
    for /f "delims=" %%P in ('where py.exe 2^>nul') do (
        if not defined PYEXE set "PYEXE=%%P"
    )
)
if not defined PYEXE (
    echo ERROR: Python was not found in PATH.
    pause
    exit /b 5
)

set "LANIP=%~1"
if defined LANIP (
    echo Launching v75 with LAN IP %LANIP%
    "%PYEXE%" "%~dp0hon_v49_dashboard.py" "%LANIP%"
) else (
    echo Launching v75 with automatic LAN-IP detection.
    "%PYEXE%" "%~dp0hon_v49_dashboard.py"
)

endlocal
