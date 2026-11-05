@echo off
setlocal EnableExtensions

set "HON_HOME=%~dp0work\manual-test\Heroes of Newerth"
set "THORGOR_NATIVE_VARIANT=selection-recovery"
set "SERVER_IP=%~2"
if not defined SERVER_IP set "SERVER_IP=127.0.0.1"

if not exist "%HON_HOME%\hon.exe" (
    echo Repaired HoN copy missing: "%HON_HOME%"
    exit /b 3
)

if "%~1"=="" goto server
if /i "%~1"=="server" goto server
if /i "%~1"=="clients" goto clients
if /i "%~1"=="verify" goto verify
echo Usage: %~nx0 [server^|clients^|verify] [server-ip]
exit /b 2

:server
echo Starting ThorGor selection-recovery from "%HON_HOME%"
call "%~dp0START_STACK.bat" "%SERVER_IP%"
exit /b %ERRORLEVEL%

:verify
pushd "%~dp0"
python -m thorgor patches verify --hon-home "%HON_HOME%"
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%

:clients
call "%~f0" verify
if errorlevel 1 exit /b 4
pushd "%~dp0"
python -m thorgor remote-setup --hon-home "%HON_HOME%" --server-ip "%SERVER_IP%"
if errorlevel 1 (
    popd
    exit /b 5
)
python -m thorgor remote-client --hon-home "%HON_HOME%" --server-ip "%SERVER_IP%" --instances 2
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
