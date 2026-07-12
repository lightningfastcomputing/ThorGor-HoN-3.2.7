@echo off
setlocal
cd /d "%~dp0"

:menu
cls
echo ============================================================
echo ThorGor HoN Local Account Manager v24
echo ============================================================
echo 1. List accounts
echo 2. Add or reset an account password
echo 3. Disable an account
echo 4. Enable an account
echo 5. Delete an account
echo 6. Exit
echo.
set /p choice=Choose an option: 

if "%choice%"=="1" goto list
if "%choice%"=="2" goto add
if "%choice%"=="3" goto disable
if "%choice%"=="4" goto enable
if "%choice%"=="5" goto delete
if "%choice%"=="6" exit /b 0
goto menu

:list
python thorgor_hon_sandboxed_masterserver_v24.py --list-accounts
pause
goto menu

:add
set /p username=Username: 
set /p password=Password: 
set /p nickname=Nickname [leave blank to use username]: 
if "%nickname%"=="" (
    python thorgor_hon_sandboxed_masterserver_v24.py --add-account "%username%" "%password%"
) else (
    python thorgor_hon_sandboxed_masterserver_v24.py --add-account "%username%" "%password%" --nickname "%nickname%"
)
pause
goto menu

:disable
set /p username=Username to disable: 
python thorgor_hon_sandboxed_masterserver_v24.py --disable-account "%username%"
pause
goto menu

:enable
set /p username=Username to enable: 
python thorgor_hon_sandboxed_masterserver_v24.py --enable-account "%username%"
pause
goto menu

:delete
set /p username=Username to permanently delete: 
python thorgor_hon_sandboxed_masterserver_v24.py --delete-account "%username%"
pause
goto menu
