@echo off
setlocal
cd /d "%~dp0"
set "SHOWCASE_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "SHOWCASE_PYTHON=.venv\Scripts\python.exe"
"%SHOWCASE_PYTHON%" tools\run_showcase_web.py --open
if errorlevel 1 echo Showcase failed. Read the error above; do not present an older output as this run.
pause
