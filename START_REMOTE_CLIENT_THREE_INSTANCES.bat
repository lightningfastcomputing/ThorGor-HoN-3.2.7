@echo off
setlocal EnableExtensions

set "SERVER_IP=%~1"
if not defined SERVER_IP set /p "SERVER_IP=Enter the ThorGor server LAN IPv4 address: "
if not defined SERVER_IP exit /b 3

call "%~dp0START_REMOTE_CLIENT.bat" "%SERVER_IP%" 3
exit /b %ERRORLEVEL%
