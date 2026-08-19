@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Run run.bat once first so Python packages are installed.
  pause
  exit /b 1
)

echo Installing the desktop window library...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Install failed.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" make_icon.py

echo Creating Start Menu and Desktop shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-shortcuts.ps1"

echo.
echo 36x Bindery is installed for this Windows user.
echo Open it from the Start menu or the Desktop icon named 36x Bindery.
echo It opens in its own window — not as a browser tab.
echo.
pause
