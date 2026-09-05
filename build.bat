@echo off
cd /d "D:\OpenCode_Arhive\Talker Box"

echo ========================================
echo Talker Box - Build Script
echo ========================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first!
    pause
    exit /b 1
)

echo [1/4] Installing build dependencies...
venv\Scripts\python.exe -m pip install pyinstaller

echo.
echo [2/4] Building executable...
cd src
..\venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name TalkerBox --add-data "../sounds;sounds" --add-data "../ads.json;." --add-data "hotkey_listener.py;." main.py
cd ..

echo.
echo [3/4] Copying files...
mkdir dist\TalkerBox 2>nul
copy dist\TalkerBox\TalkerBox.exe dist\TalkerBox\
copy ads.json dist\TalkerBox\
xcopy /E /I /Y sounds dist\TalkerBox\sounds
copy talkerbox.png dist\TalkerBox\

echo.
echo [4/4] Done!
echo.
echo Executable: dist\TalkerBox\TalkerBox.exe
echo Now open installer\talkerbox.iss in Inno Setup and click Compile
echo.
pause
