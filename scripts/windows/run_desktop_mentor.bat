@echo off
setlocal EnableExtensions
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"

set "LOG=%ROOT%\windows-run.log"
echo ==== MyDesktopMentor run %date% %time% ==== > "%LOG%"

set "ENV_NAME=%DESKTOP_MENTOR_CONDA_ENV_NAME%"
if "%ENV_NAME%"=="" set "ENV_NAME=my-desktop-mentor"

set "ENV_PREFIX=%DESKTOP_MENTOR_CONDA_PREFIX%"

set "PYTHON_CMD="
call :try_python "%DESKTOP_MENTOR_PYTHON%"
if not "%ENV_PREFIX%"=="" call :try_python "%ENV_PREFIX%\python.exe"
call :try_python "%CONDA_PREFIX%\python.exe"
call :try_common_conda_envs
call :try_conda_base_env
call :try_python "%ROOT%\.conda\python.exe"

if "%PYTHON_CMD%"=="" (
  where py >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if "%PYTHON_CMD%"=="" (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)

if "%PYTHON_CMD%"=="" (
  echo Python not found.
  echo Create the Conda environment first:
  echo   scripts\windows\setup_conda_env.bat
  echo Python not found. >> "%LOG%"
  pause
  exit /b 1
)

echo Using: %PYTHON_CMD%
echo Using: %PYTHON_CMD% >> "%LOG%"

%PYTHON_CMD% -c "from PySide6.QtCore import Qt; from PySide6.QtWebEngineWidgets import QWebEngineView; import markdown_it, latex2mathml, pygments, qasync" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo Required Python dependencies are missing from:
  echo   %PYTHON_CMD%
  echo Create or repair the Conda environment:
  echo   scripts\windows\setup_conda_env.bat
  echo Required Python dependencies are missing. >> "%LOG%"
  pause
  exit /b 1
)

%PYTHON_CMD% desktop_mentor.py %* >> "%LOG%" 2>&1
if errorlevel 1 (
  echo MyDesktopMentor crashed. See:
  echo   %LOG%
  pause
  exit /b 1
)
exit /b 0

:try_python
if not "%PYTHON_CMD%"=="" exit /b 0
if "%~1"=="" exit /b 0
if exist "%~1" set "PYTHON_CMD="%~1""
exit /b 0

:try_common_conda_envs
if not "%PYTHON_CMD%"=="" exit /b 0
call :try_python "%USERPROFILE%\miniconda3\envs\%ENV_NAME%\python.exe"
call :try_python "%USERPROFILE%\anaconda3\envs\%ENV_NAME%\python.exe"
call :try_python "%LOCALAPPDATA%\miniconda3\envs\%ENV_NAME%\python.exe"
call :try_python "%LOCALAPPDATA%\anaconda3\envs\%ENV_NAME%\python.exe"
exit /b 0

:try_conda_base_env
if not "%PYTHON_CMD%"=="" exit /b 0
set "CONDA_CMD="
if not "%CONDA_EXE%"=="" if exist "%CONDA_EXE%" set "CONDA_CMD=%CONDA_EXE%"
if "%CONDA_CMD%"=="" (
  for /f "delims=" %%I in ('where conda 2^>nul') do (
    if "%CONDA_CMD%"=="" set "CONDA_CMD=%%I"
  )
)
if "%CONDA_CMD%"=="" exit /b 0
for /f "delims=" %%B in ('"%CONDA_CMD%" info --base 2^>nul') do (
  call :try_python "%%B\envs\%ENV_NAME%\python.exe"
)
exit /b 0
