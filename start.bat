@echo off
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Virtual environment not found. Running setup...
    call setup.bat
)

venv\Scripts\python.exe src\main.py
