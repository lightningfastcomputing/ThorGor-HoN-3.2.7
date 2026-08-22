@echo off
setlocal EnableExtensions
set "SERVER_IP=%~1"
if not defined SERVER_IP set /p "SERVER_IP=Enter the LAN server IPv4 address: "
if not defined SERVER_IP exit /b 3

if not defined HON_HOME set "HON_HOME=C:\Program Files (x86)\Heroes of Newerth"
if not exist "%HON_HOME%\hon.exe" (
  echo hon.exe was not found at "%HON_HOME%\hon.exe"
  pause
  exit /b 2
)

echo.
echo ThorGor v77 local LAN player
echo   HoN folder : %HON_HOME%
echo   Server IP  : %SERVER_IP%
echo.
echo Generating and installing K2 v77 plus cgame v61 from this PC's verified game files...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p=Start-Process powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','""%~dp0INSTALL_V77_PATCHES.ps1""','-HonHome','""%HON_HOME%""'; exit $p.ExitCode"
if errorlevel 1 (
  echo Failed to install the source-generated v77/v61 patches. Please accept the UAC prompt.
  pause
  exit /b 5
)

echo Verifying K2 v77 and cgame v61 before launch...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$k=(Get-FileHash -LiteralPath '%HON_HOME%\k2.dll' -Algorithm SHA256).Hash; $c=(Get-FileHash -LiteralPath '%HON_HOME%\game\cgame.dll' -Algorithm SHA256).Hash; Write-Host ('Installed k2 SHA256:    ' + $k); Write-Host ('Installed cgame SHA256: ' + $c); if($k -eq '25B1BB066FE3166BF83A4AA52D6FBB0B9FB972F43161F3D73DFA930090CE7026' -and $c -eq '88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988'){Write-Host '[OK] K2 v77 and cgame v61 will be loaded by the new player.' -ForegroundColor Green; exit 0}else{Write-Host '[FAIL] Refusing to launch with DLLs other than v77/v61.' -ForegroundColor Red; exit 8}"
if errorlevel 1 (
  echo.
  echo The installed game DLLs did not pass v77/v61 verification.
  pause
  exit /b 8
)

echo Configuring legacy HoN chat hostname to the ThorGor server...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p=Start-Process powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','""%~dp0remote-client\SET_CHAT_HOST.ps1""','-ServerIP','%SERVER_IP%'; exit $p.ExitCode"
if errorlevel 1 (
  echo Failed to update the chat hostname. Please accept the UAC prompt.
  pause
  exit /b 5
)

echo Testing server chat port %SERVER_IP%:11031...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$t=Test-NetConnection -ComputerName '%SERVER_IP%' -Port 11031 -WarningAction SilentlyContinue; if($t.TcpTestSucceeded){Write-Host '[OK] Chat TCP 11031 reachable' -ForegroundColor Green; exit 0}else{Write-Host '[FAIL] Chat TCP 11031 is blocked/unreachable' -ForegroundColor Red; exit 6}"
if errorlevel 1 (
  echo.
  echo The player cannot reach the server chat listener yet.
  echo Verify the server dashboard is running and its firewall rules were accepted.
  pause
  exit /b 6
)

echo Starting HoN against ThorGor LAN backend at %SERVER_IP%
echo Login with: pwnrbwnr / pwnrbwnr
start "HoN Local Player - ThorGor v77 LAN" /D "%HON_HOME%" hon.exe -masterserver %SERVER_IP%
exit /b 0
