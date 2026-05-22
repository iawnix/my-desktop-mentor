@echo off
setlocal EnableExtensions
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"

set "ENV_PREFIX=%DESKTOP_MENTOR_CONDA_PREFIX%"
set "ENV_NAME=%DESKTOP_MENTOR_CONDA_ENV_NAME%"
if "%ENV_PREFIX%"=="" if "%ENV_NAME%"=="" set "ENV_NAME=my-desktop-mentor"

set "PYTHON_VERSION=%DESKTOP_MENTOR_PYTHON_VERSION%"
if "%PYTHON_VERSION%"=="" set "PYTHON_VERSION=3.12"

set "CONDA_CMD="
if not "%CONDA_EXE%"=="" if exist "%CONDA_EXE%" set "CONDA_CMD=%CONDA_EXE%"
if "%CONDA_CMD%"=="" (
  for /f "delims=" %%I in ('where conda 2^>nul') do (
    if "%CONDA_CMD%"=="" set "CONDA_CMD=%%I"
  )
)

if "%CONDA_CMD%"=="" (
  echo Conda was not found.
  echo Install Miniconda/Anaconda or set CONDA_EXE to conda.exe.
  pause
  exit /b 1
)

if not "%ENV_NAME%"=="" (
  "%CONDA_CMD%" run -n "%ENV_NAME%" python -c "import sys" >nul 2>nul
  if errorlevel 1 (
    echo Creating Conda environment named:
    echo   %ENV_NAME%
    "%CONDA_CMD%" create -y -n "%ENV_NAME%" "python=%PYTHON_VERSION%" pip
    if errorlevel 1 (
      echo Failed to create Conda environment.
      pause
      exit /b 1
    )
  ) else (
    echo Using existing Conda environment:
    echo   %ENV_NAME%
  )
) else (
  if not exist "%ENV_PREFIX%\python.exe" (
    echo Creating Conda environment at:
    echo   %ENV_PREFIX%
    "%CONDA_CMD%" create -y -p "%ENV_PREFIX%" "python=%PYTHON_VERSION%" pip
    if errorlevel 1 (
      echo Failed to create Conda environment.
      pause
      exit /b 1
    )
  ) else (
    echo Using existing Conda environment:
    echo   %ENV_PREFIX%
  )
)

if not "%ENV_NAME%"=="" (
  set "PYTHON_CMD="%CONDA_CMD%" run -n "%ENV_NAME%" python"
) else (
  set "PYTHON_CMD="%ENV_PREFIX%\python.exe""
)

%PYTHON_CMD% -m pip install --upgrade pip
if errorlevel 1 (
  echo Failed to upgrade pip.
  pause
  exit /b 1
)

%PYTHON_CMD% -m pip install -r "%ROOT%\requirements.txt"
if errorlevel 1 (
  echo Failed to install requirements.
  pause
  exit /b 1
)

%PYTHON_CMD% -c "from PySide6.QtCore import Qt; from PySide6.QtWebEngineWidgets import QWebEngineView; import markdown_it, latex2mathml, pygments, qasync; print('desktop mentor conda environment is ready')"
if errorlevel 1 (
  echo Runtime import check failed.
  pause
  exit /b 1
)

echo Done.
exit /b 0
