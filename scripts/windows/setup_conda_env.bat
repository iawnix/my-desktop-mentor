@echo off
setlocal EnableExtensions
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"

set "ENV_PREFIX=%DESKTOP_MENTOR_CONDA_PREFIX%"
if "%ENV_PREFIX%"=="" set "ENV_PREFIX=%ROOT%\.conda"

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

"%ENV_PREFIX%\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  echo Failed to upgrade pip.
  pause
  exit /b 1
)

"%ENV_PREFIX%\python.exe" -m pip install -r "%ROOT%\requirements.txt"
if errorlevel 1 (
  echo Failed to install requirements.
  pause
  exit /b 1
)

"%ENV_PREFIX%\python.exe" -c "from PySide6.QtCore import Qt; from PySide6.QtWebEngineWidgets import QWebEngineView; import markdown_it, latex2mathml, pygments, qasync; print('desktop mentor conda environment is ready')"
if errorlevel 1 (
  echo Runtime import check failed.
  pause
  exit /b 1
)

echo Done.
exit /b 0
