@echo off
cd /d "%~dp0"
chcp 65001 >nul

echo === Talker Box Setup ===
echo.

rem --- поиск Python 3.13 (установлен без PATH — перебираем известные места) ---
set "PY="
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY if exist "C:\Program Files\Python313\python.exe" set "PY=C:\Program Files\Python313\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python313-32\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313-32\python.exe"
if not defined PY for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"

if not defined PY (
    echo ERROR: Python 3.13 not found.
    echo Install Python 3.13 and run this file again.
    pause
    exit /b 1
)
echo Python: %PY%
"%PY%" -V

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    "%PY%" -m venv venv
    if errorlevel 1 (
        echo ERROR: failed to create venv
        pause
        exit /b 1
    )
)

echo.
echo Installing dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed
    pause
    exit /b 1
)

echo.
echo Setup complete. Run start.bat to launch.
pause
