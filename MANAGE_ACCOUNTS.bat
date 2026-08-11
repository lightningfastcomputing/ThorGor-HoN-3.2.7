@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHON_EXE="
for /f "usebackq delims=" %%P in (`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0FIND_PYTHON.ps1" 2^>nul`) do set "PYTHON_EXE=%%P"
if not defined PYTHON_EXE (
  echo Python 3.10 or newer was not found.
  echo Install it with: winget install --exact --id Python.Python.3.14
  pause
  exit /b 4
)
"%PYTHON_EXE%" "%~dp0manage_accounts_v43.py"
if errorlevel 1 (
  echo Account manager failed.
  pause
  exit /b 1
)
pause
