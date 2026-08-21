@echo off
setlocal
cd /d "%~dp0"

echo ThorGor v74 one-shot joined-client hero-list fix
echo - Repairs only the exact truncated picking packet seen in v73.
echo - Copies validated state blocks 3 through 8 from host delivery to joiner delivery.
echo - Does not use periodic retransmission and does not change HoN DLLs.
echo.

echo Resetting volatile ThorGor runtime state for a clean test...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RESET_V42.ps1"
if errorlevel 1 (
    echo ERROR: ThorGor runtime-state reset failed. Do not continue this run.
    pause
    exit /b 1
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
    exit /b 1
)

set "LANIP=%~1"
if defined LANIP (
    echo Launching v74 with LAN IP %LANIP%
    "%PYEXE%" "%~dp0hon_v49_dashboard.py" "%LANIP%"
) else (
    echo Launching v74 with automatic LAN-IP detection.
    "%PYEXE%" "%~dp0hon_v49_dashboard.py"
)

endlocal
