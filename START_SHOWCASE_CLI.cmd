@echo off
setlocal
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
set "SHOWCASE_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "SHOWCASE_PYTHON=.venv\Scripts\python.exe"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
echo Zip2CAD Library Inference - Independent Step Commands
echo.
echo Run each command when you are ready:
echo   python step1.py   - Validate inputs and weights
echo   python step2.py   - Run pretrained neural inference
echo   python step3.py   - Export predicted geometry and SKP
echo   python step4.py   - Prepare full-campus deliverable
echo   python step5.py   - Verify results and open output folder
echo.
echo Each command returns here. No next step starts automatically.
echo To restart an unfinished run: python step1.py --new-run
cmd /d /k "echo Ready for step commands."
