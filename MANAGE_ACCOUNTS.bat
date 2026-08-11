@echo off
setlocal EnableExtensions
cd /d "%~dp0"
python "%~dp0manage_accounts_v43.py"
if errorlevel 1 (
  echo Account manager failed.
  pause
  exit /b 1
)
pause
