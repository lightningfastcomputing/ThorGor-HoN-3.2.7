@echo off
setlocal EnableExtensions EnableDelayedExpansion

for %%I in ("%~dp0.") do set "THORGOR_PACKAGE=%%~fI"

set "PYEXE="
for /f "delims=" %%P in ('where python.exe 2^>nul') do (
    if not defined PYEXE set "PYEXE=%%P"
)
if not defined PYEXE (
    echo ERROR: Python was not found on PATH.
    pause
    exit /b 6
)

title ThorGor Account Manager
echo ThorGor HoN 3.2.7 LAN Sandbox account manager
echo   Package: !THORGOR_PACKAGE!
echo   Database: !THORGOR_PACKAGE!\var\thorgor_accounts.db

pushd "!THORGOR_PACKAGE!"
"!PYEXE!" -m thorgor accounts
set "ACCOUNT_EXIT=!ERRORLEVEL!"
popd

if not "!ACCOUNT_EXIT!"=="0" (
    echo.
    echo ERROR: ThorGor account manager exited with code !ACCOUNT_EXIT!.
    pause
)
exit /b !ACCOUNT_EXIT!
