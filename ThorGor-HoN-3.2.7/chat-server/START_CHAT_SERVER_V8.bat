@echo off
cd /d "%~dp0"
title ThorGor HoN LAN Chat Server v8

rem Always use the account database created by the bundled v24 master server.
set "THORGOR_ACCOUNT_DB=%~dp0..\thorgor_accounts.db"

python thorgor_hon_chatserver_v8.py --db "%THORGOR_ACCOUNT_DB%"

echo.
echo Server exited with code %ERRORLEVEL%.
pause
