@echo off
cd /d "D:\OpenCode_Arhive\Talker Box"

echo === Talker Box Setup ===

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Installing dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt

echo.
echo Setup complete. Run start.bat to launch.
pause
