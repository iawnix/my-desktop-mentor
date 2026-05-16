@echo off
setlocal
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"

set "LOG=%ROOT%\windows-build.log"
echo ==== MyDesktopMentor build %date% %time% ==== > "%LOG%"

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)

if "%PYTHON_CMD%"=="" (
  echo Python not found. Install Python 3.11+ from python.org and enable "Add python.exe to PATH".
  echo Python not found. >> "%LOG%"
  pause
  exit /b 1
)

echo Using: %PYTHON_CMD%
echo Using: %PYTHON_CMD% >> "%LOG%"

%PYTHON_CMD% -m pip install --upgrade pip >> "%LOG%" 2>&1
if errorlevel 1 goto build_failed

%PYTHON_CMD% -m pip install -r packaging\windows\requirements-windows.txt >> "%LOG%" 2>&1
if errorlevel 1 goto build_failed

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

%PYTHON_CMD% -m PyInstaller packaging\windows\desktop_mentor.spec --noconfirm --clean >> "%LOG%" 2>&1
if errorlevel 1 goto build_failed

echo.
echo Built:
echo   %cd%\dist\MyDesktopMentor.exe
echo.
echo Run that exe. Runtime config is stored under %%APPDATA%%\MyDesktopMentor\config.json.
echo Build completed. >> "%LOG%"
pause
exit /b 0

:build_failed
echo.
echo Build failed. See:
echo   %LOG%
pause
exit /b 1
