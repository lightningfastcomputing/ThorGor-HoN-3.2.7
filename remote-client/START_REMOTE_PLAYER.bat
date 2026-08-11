@echo off
setlocal EnableExtensions
set "SERVER_IP=%~1"
if not defined SERVER_IP set /p "SERVER_IP=Enter DEV/SERVER PC LAN IPv4 address: "
if not defined SERVER_IP exit /b 3

set "HON_HOME=C:\Program Files (x86)\Heroes of Newerth"
if not exist "%HON_HOME%\hon.exe" (
  echo hon.exe was not found at "%HON_HOME%\hon.exe"
  pause
  exit /b 2
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\CHECK_HON_PLAYER_NOT_RUNNING.ps1"
if errorlevel 1 (
  echo.
  echo Close only the HoN player client, then run this launcher again.
  echo The ThorGor manager and dedicated slave may remain running.
  echo v61 cannot protect a cgame.dll that an older process already loaded.
  pause
  exit /b 7
)

echo.
echo ThorGor LAN client
echo   HoN folder : %HON_HOME%
echo   Server IP  : %SERVER_IP%
echo.
echo Generating and installing the v57/v61 patches from this PC's verified game files...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p=Start-Process powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','""%~dp0..\INSTALL_V61_PATCHES.ps1""','-HonHome','""%HON_HOME%""'; exit $p.ExitCode"
if errorlevel 1 (
  echo Failed to install the source-generated patches. Please accept the UAC prompt.
  pause
  exit /b 5
)

echo Verifying the installed v61 DLL before launch...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$h=(Get-FileHash -LiteralPath '%HON_HOME%\game\cgame.dll' -Algorithm SHA256).Hash; Write-Host ('Installed cgame SHA256: ' + $h); if($h -eq '88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988'){Write-Host '[OK] v61 is installed and will be loaded by the new process.' -ForegroundColor Green; exit 0}else{Write-Host '[FAIL] Refusing to launch: cgame.dll is not v61.' -ForegroundColor Red; exit 8}"
if errorlevel 1 (
  echo.
  echo The installed game DLL did not pass v61 verification.
  pause
  exit /b 8
)

echo Configuring legacy HoN chat hostname to the ThorGor server...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p=Start-Process powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','""%~dp0SET_CHAT_HOST.ps1""','-ServerIP','%SERVER_IP%'; exit $p.ExitCode"
if errorlevel 1 (
  echo Failed to update the chat hostname. Please accept the UAC prompt.
  pause
  exit /b 5
)

echo Testing server chat port %SERVER_IP%:11031...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$t=Test-NetConnection -ComputerName '%SERVER_IP%' -Port 11031 -WarningAction SilentlyContinue; if($t.TcpTestSucceeded){Write-Host '[OK] Chat TCP 11031 reachable' -ForegroundColor Green; exit 0}else{Write-Host '[FAIL] Chat TCP 11031 is blocked/unreachable' -ForegroundColor Red; exit 6}"
if errorlevel 1 (
  echo.
  echo The client cannot reach the server chat listener yet.
  echo Verify the server dashboard is running and accept its Firewall UAC prompt.
  pause
  exit /b 6
)

echo Starting HoN against ThorGor LAN backend at %SERVER_IP%
echo Login with: player / player
start "HoN Remote Player - ThorGor v61 LAN" /D "%HON_HOME%" hon.exe -masterserver %SERVER_IP%
exit /b 0
