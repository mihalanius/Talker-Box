@echo off
cd /d "%~dp0"

echo === Talker Box Setup ===

if not exist "venv" (
    echo Creating virtual environment...
    "C:\Users\Glab\AppData\Local\Programs\Python\Python313\python.exe" -m venv venv
)

echo Installing dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt

echo.
echo Setup complete. Run start.bat to launch.
pause
