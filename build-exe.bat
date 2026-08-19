@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Run run.bat once first so the local Python environment exists.
  pause
  exit /b 1
)

echo Installing PyInstaller...
".venv\Scripts\python.exe" -m pip install "pyinstaller==6.13.0"
if errorlevel 1 exit /b 1

echo.
echo Building Bindery.exe ^(this can take a few minutes^)...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean bindery.spec
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

echo.
echo Packing a zip you can send to people...
if exist "dist\Bindery-windows.zip" del "dist\Bindery-windows.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\Bindery\*' -DestinationPath 'dist\Bindery-windows.zip' -Force"

echo.
echo Done.
echo   App folder:  dist\Bindery\Bindery.exe
echo   Share zip:   dist\Bindery-windows.zip
echo Recipients unzip anywhere and double-click Bindery.exe. No Python needed.
echo Windows may warn that the file is unsigned. That is normal for an unsigned local app.
pause
