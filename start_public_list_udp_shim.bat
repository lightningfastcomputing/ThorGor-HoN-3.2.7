@echo off
cd /d "%~dp0"
echo Starting ThorGor HoN UDP public-list shim...
echo.
python hon_udp_shim.py --preset thorgor-public-list
pause
