@echo off
setlocal
cd /d "%~dp0"

set "FC26_PYTHON="
if exist ".venv\Scripts\python.exe" set "FC26_PYTHON=.venv\Scripts\python.exe"
if not defined FC26_PYTHON if exist "C:\anaconda3\python.exe" set "FC26_PYTHON=C:\anaconda3\python.exe"
if not defined FC26_PYTHON if exist "C:\Python314\python.exe" set "FC26_PYTHON=C:\Python314\python.exe"
if not defined FC26_PYTHON set "FC26_PYTHON=python"

"%FC26_PYTHON%" -c "import flask, waitress, openpyxl" >nul 2>nul
if errorlevel 1 (
  echo Installing Python dependencies...
  "%FC26_PYTHON%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Dependency installation failed. Check Python and network settings.
    pause
    exit /b 1
  )
)

echo Starting FC26 Save Editor...
"%FC26_PYTHON%" web_app.py
pause
