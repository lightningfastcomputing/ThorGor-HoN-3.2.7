@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem The thorgor package is portable and may be moved with no adjacent legacy files.
for %%I in ("%~dp0.") do set "THORGOR_PACKAGE=%%~fI"

if not defined HON_HOME set "HON_HOME=C:\intelprop\Heroes of Newerth"
set "THORGOR_HON_HOME=!HON_HOME!"

if not exist "!HON_HOME!\hon.exe" (
    echo ERROR: hon.exe was not found:
    echo   !HON_HOME!\hon.exe
    echo.
    echo Set HON_HOME before launching to use another installation.
    pause
    exit /b 3
)

set "PYEXE="
for /f "delims=" %%P in ('where python.exe 2^>nul') do (
    if not defined PYEXE set "PYEXE=%%P"
)
if not defined PYEXE (
    echo ERROR: Python was not found on PATH.
    pause
    exit /b 6
)

echo ThorGor HoN 3.2.7 LAN Sandbox launcher
echo   Package: !THORGOR_PACKAGE!
echo   HoN:     !HON_HOME!
echo.

pushd "!THORGOR_PACKAGE!"

echo Installing or verifying supported binary patches...
"!PYEXE!" -m thorgor patches install --hon-home "!HON_HOME!"
set "SETUP_EXIT=!ERRORLEVEL!"
if not "!SETUP_EXIT!"=="0" (
    popd
    echo.
    echo ERROR: ThorGor binary verification or installation failed.
    pause
    exit /b 4
)

echo Resetting volatile ThorGor runtime state...
"!PYEXE!" -m thorgor cleanup
if not "!ERRORLEVEL!"=="0" (
    popd
    echo ERROR: ThorGor process cleanup failed.
    pause
    exit /b 5
)
"!PYEXE!" -m thorgor reset-state
set "RESET_EXIT=!ERRORLEVEL!"
if not "!RESET_EXIT!"=="0" (
    popd
    echo.
    echo ERROR: ThorGor runtime-state reset failed.
    pause
    exit /b 5
)

set "LAN_IP=%~1"
if defined LAN_IP (
    echo Launching ThorGor dashboard for LAN IP !LAN_IP!...
    "!PYEXE!" -m thorgor dashboard "!LAN_IP!"
) else (
    echo Launching ThorGor dashboard with automatic LAN-IP detection...
    "!PYEXE!" -m thorgor dashboard
)
set "DASHBOARD_EXIT=!ERRORLEVEL!"
popd

if not "!DASHBOARD_EXIT!"=="0" (
    echo.
    echo ERROR: ThorGor dashboard exited with code !DASHBOARD_EXIT!.
    pause
)

exit /b !DASHBOARD_EXIT!
