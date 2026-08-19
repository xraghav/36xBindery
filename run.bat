@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1 && set PY=py -3
if not defined PY (
  where python >nul 2>&1 && set PY=python
)
if not defined PY (
  echo Python 3 was not found. Install it from https://www.python.org/downloads/ then run this again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating local environment...
  %PY% -m venv .venv
)

echo Installing Bindery packages into .venv ^(first run only takes a minute^)...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Install failed.
  pause
  exit /b 1
)

echo.
echo Starting Bindery on http://127.0.0.1:8741
echo Leave this window open. Close it to stop the desk.
echo.
".venv\Scripts\python.exe" server.py
