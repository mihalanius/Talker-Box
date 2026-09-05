@echo off
cd /d "D:\OpenCode_Arhive\Talker Box"

if not exist "venv\Scripts\python.exe" (
    echo Virtual environment not found. Running setup...
    call setup.bat
)

venv\Scripts\python.exe src\main.py