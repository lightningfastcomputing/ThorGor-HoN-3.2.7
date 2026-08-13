@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "%~dp0ThorGorAccountManager.exe" (
  echo ThorGorAccountManager.exe was not found.
  echo Download a complete release or run BUILD_COMPILED.ps1.
  pause
  exit /b 4
)
"%~dp0ThorGorAccountManager.exe"
if errorlevel 1 (
  echo Account manager failed.
  pause
  exit /b 1
)
pause
