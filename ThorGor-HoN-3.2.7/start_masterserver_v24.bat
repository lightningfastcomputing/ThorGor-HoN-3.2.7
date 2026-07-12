@echo off
cd /d "%~dp0"
echo Starting ThorGor HoN Sandboxed Masterserver v24...
echo.
python thorgor_hon_sandboxed_masterserver_v24.py --password-chain pre-md5
pause
