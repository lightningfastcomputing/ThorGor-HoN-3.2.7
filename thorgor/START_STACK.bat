@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem This folder is a self-contained Python package plus frozen v77 runtime.
rem It can be copied anywhere as long as its directory name remains thorgor.
for %%I in ("%~dp0.") do set "THORGOR_PACKAGE=%%~fI"
for %%I in ("%~dp0..") do set "THORGOR_PARENT=%%~fI"
set "THORGOR_RUNTIME=!THORGOR_PACKAGE!\runtime"

if not defined HON_HOME set "HON_HOME=C:\intelprop\Heroes of Newerth"
set "THORGOR_HON_HOME=!HON_HOME!"

set "WINDOWS_POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "!WINDOWS_POWERSHELL!" (
    echo ERROR: Windows PowerShell was not found:
    echo   !WINDOWS_POWERSHELL!
    pause
    exit /b 2
)

rem Codex and PowerShell 7 sessions may export a module path that hides the
rem inbox Windows PowerShell modules. Normalize both executable and module
rem lookup before running any installer, including nested helper shells.
set "PATH=%SystemRoot%\System32\WindowsPowerShell\v1.0;!PATH!"
set "PSModulePath=%SystemRoot%\System32\WindowsPowerShell\v1.0\Modules;%ProgramFiles%\WindowsPowerShell\Modules"

if not exist "!HON_HOME!\hon.exe" (
    echo ERROR: hon.exe was not found:
    echo   !HON_HOME!\hon.exe
    echo.
    echo Set HON_HOME before launching to use another installation.
    pause
    exit /b 3
)

echo ThorGor refactored stack launcher
echo   Package: !THORGOR_PACKAGE!
echo   Runtime: !THORGOR_RUNTIME!
echo   HoN:     !HON_HOME!
echo.

for %%F in ("INSTALL_V77_PATCHES.ps1" "RESET_V42.ps1" "hon_v49_dashboard.py") do (
    if not exist "!THORGOR_RUNTIME!\%%~F" (
        echo ERROR: Portable runtime file is missing:
        echo   !THORGOR_RUNTIME!\%%~F
        echo.
        echo Copy the complete thorgor folder, including its runtime directory.
        pause
        exit /b 4
    )
)

echo Installing or verifying K2 v77 and cgame v61...
"!WINDOWS_POWERSHELL!" -NoProfile -ExecutionPolicy Bypass -File "!THORGOR_RUNTIME!\INSTALL_V77_PATCHES.ps1" -HonHome "!HON_HOME!"
set "SETUP_EXIT=!ERRORLEVEL!"
if not "!SETUP_EXIT!"=="0" (
    echo.
    echo ERROR: ThorGor binary verification or installation failed.
    pause
    exit /b 4
)

echo Resetting volatile ThorGor runtime state...
"!WINDOWS_POWERSHELL!" -NoProfile -ExecutionPolicy Bypass -File "!THORGOR_RUNTIME!\RESET_V42.ps1"
set "RESET_EXIT=!ERRORLEVEL!"
if not "!RESET_EXIT!"=="0" (
    echo.
    echo ERROR: ThorGor runtime-state reset failed.
    pause
    exit /b 5
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

set "LAN_IP=%~1"
pushd "!THORGOR_PARENT!"
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
