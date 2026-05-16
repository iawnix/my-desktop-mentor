@echo off
setlocal
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"

set "LOG=%ROOT%\windows-run.log"
echo ==== MyDesktopMentor run %date% %time% ==== > "%LOG%"

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)

if "%PYTHON_CMD%"=="" (
  echo Python not found.
  echo Install Python 3.11+ from https://www.python.org/downloads/
  echo During install, enable "Add python.exe to PATH".
  echo Python not found. >> "%LOG%"
  pause
  exit /b 1
)

echo Using: %PYTHON_CMD%
echo Using: %PYTHON_CMD% >> "%LOG%"

%PYTHON_CMD% -c "import PySide6" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo PySide6 not found. Installing requirements...
  echo PySide6 not found. Installing requirements... >> "%LOG%"
  %PYTHON_CMD% -m pip install -r requirements.txt >> "%LOG%" 2>&1
  if errorlevel 1 (
    echo Failed to install requirements. See:
    echo   %LOG%
    pause
    exit /b 1
  )
)

%PYTHON_CMD% desktop_mentor.py %* >> "%LOG%" 2>&1
if errorlevel 1 (
  echo MyDesktopMentor crashed. See:
  echo   %LOG%
  pause
  exit /b 1
)
