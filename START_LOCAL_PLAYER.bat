@echo off
setlocal EnableExtensions
set "SERVER_IP=%~1"
if not defined SERVER_IP set /p "SERVER_IP=Enter the LAN server IPv4 address: "
if not defined SERVER_IP exit /b 2

set "HON_HOME="
if exist "C:\Program Files (x86)\Heroes of Newerth\hon.exe" set "HON_HOME=C:\Program Files (x86)\Heroes of Newerth"
if not defined HON_HOME if exist "%CD%\hon.exe" set "HON_HOME=%CD%"
if not defined HON_HOME set /p "HON_HOME=Enter the full HoN 3.2.7.1 installation folder: "
if not exist "%HON_HOME%\hon.exe" (
  echo hon.exe was not found in "%HON_HOME%".
  pause
  exit /b 2
)

start "ThorGor LAN Player" /D "%HON_HOME%" hon.exe -masterserver %SERVER_IP%
exit /b 0
