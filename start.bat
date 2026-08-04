@echo off
chcp 65001 >nul 2>&1
setlocal
REM --- Amazon AI Growth OS launcher (safe for non-ASCII project paths) ---
set "ROOT=%~dp0"
set "VENV=C:\Users\86131\.workbuddy\binaries\python\envs\amazon_os"
set "PY=C:\Users\86131\.workbuddy\binaries\python\versions\3.13.12\python.exe"

if not exist "%VENV%\Scripts\python.exe" (
  echo [setup] First run: creating isolated venv and installing dependencies...
  "%PY%" -m venv "%VENV%"
  if errorlevel 1 (
    echo [error] Failed to create venv. Check Python at %PY%
    pause
    exit /b 1
  )
  call "%VENV%\Scripts\pip.exe" install -r "%ROOT%requirements.txt"
)

cd /d "%ROOT%backend"
if errorlevel 1 (
  echo [error] Cannot find backend folder at %ROOT%backend
  pause
  exit /b 1
)

echo [start] Starting Amazon AI Growth OS ...
call "%VENV%\Scripts\activate.bat"
python run_server.py
pause
