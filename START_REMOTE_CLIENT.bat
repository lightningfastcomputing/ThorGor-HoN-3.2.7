@echo off
setlocal EnableExtensions EnableDelayedExpansion

for %%I in ("%~dp0.") do set "THORGOR_PACKAGE=%%~fI"

set "SERVER_IP=%~1"
if not defined SERVER_IP set /p "SERVER_IP=Enter the ThorGor server LAN IPv4 address: "
if not defined SERVER_IP exit /b 3

if not defined HON_HOME set "HON_HOME=C:\intelprop\Heroes of Newerth"
if not exist "!HON_HOME!\hon.exe" (
    echo ERROR: hon.exe was not found:
    echo   !HON_HOME!\hon.exe
    echo.
    echo Set HON_HOME before launching to use another installation.
    pause
    exit /b 2
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

pushd "!THORGOR_PACKAGE!"
set "THORGOR_REMOTE_SERVER_IP=!SERVER_IP!"
"!PYEXE!" -c "import ipaddress,os; ipaddress.IPv4Address(os.environ['THORGOR_REMOTE_SERVER_IP'])" >nul 2>&1
if errorlevel 1 (
    popd
    echo ERROR: Invalid server IPv4 address: !SERVER_IP!
    pause
    exit /b 3
)

echo ThorGor HoN 3.2.7 LAN Sandbox remote client
echo   Package: !THORGOR_PACKAGE!
echo   HoN:     !HON_HOME!
echo   Server:  !SERVER_IP!
echo.
echo Installing patches and configuring the legacy chat hostname...
echo Accept the Windows administrator prompt to update the game DLLs and hosts file.

set "THORGOR_REMOTE_PYTHON=!PYEXE!"
set "THORGOR_REMOTE_PARENT=!THORGOR_PACKAGE!"
set "THORGOR_REMOTE_HON_HOME=!HON_HOME!"
set "THORGOR_REMOTE_LOG=!THORGOR_PACKAGE!\var\remote_client_setup.log"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p=Start-Process powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','""!THORGOR_PACKAGE!\REMOTE_SETUP_ADMIN.ps1""','-PythonPath','""!THORGOR_REMOTE_PYTHON!""','-ProjectRoot','""!THORGOR_REMOTE_PARENT!""','-HonHome','""!THORGOR_REMOTE_HON_HOME!""','-ServerIP','!THORGOR_REMOTE_SERVER_IP!','-LogPath','""!THORGOR_REMOTE_LOG!""'; exit $p.ExitCode"
if errorlevel 1 (
    popd
    echo.
    echo ERROR: Remote-client setup failed.
    if exist "!THORGOR_PACKAGE!\var\remote_client_setup.log" (
        echo.
        echo Setup details:
        type "!THORGOR_PACKAGE!\var\remote_client_setup.log"
    ) else (
        echo The administrator prompt may have been declined or could not open.
    )
    pause
    exit /b 5
)

echo Testing the ThorGor server and launching HoN...
"!PYEXE!" -m thorgor remote-client --hon-home "!HON_HOME!" --server-ip "!SERVER_IP!"
set "CLIENT_EXIT=!ERRORLEVEL!"
popd

if not "!CLIENT_EXIT!"=="0" (
    echo.
    echo ERROR: Remote client launch failed with code !CLIENT_EXIT!.
    echo Confirm the server dashboard is ready and TCP 11031 is reachable.
    pause
)
exit /b !CLIENT_EXIT!
