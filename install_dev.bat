@echo off
rem ============================================================
rem  Talker Box - install dev environment (all in one)
rem  Finds Python 3.13/3.12 and runs setup_dev.py
rem  Usage:  install_dev.bat            - install / repair
rem          install_dev.bat --check    - check only
rem          install_dev.bat --run      - install and launch
rem ============================================================
cd /d "%~dp0"
chcp 65001 >nul
setlocal

set "PY="
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY if exist "C:\Program Files\Python313\python.exe" set "PY=C:\Program Files\Python313\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY if exist "C:\Program Files\Python312\python.exe" set "PY=C:\Program Files\Python312\python.exe"
if not defined PY for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"

if not defined PY (
    echo.
    echo ERROR: Python not found.
    echo Install Python 3.13 ^(64-bit^) from https://www.python.org/downloads/windows/
    echo and run this file again.
    echo.
    pause
    exit /b 1
)

"%PY%" "%~dp0setup_dev.py" %*
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
