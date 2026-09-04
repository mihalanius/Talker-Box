@echo off
echo ========================================
echo Talker Box - Build Script
echo ========================================
echo.

echo [1/4] Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [2/4] Building executable...
cd src
pyinstaller --onefile --windowed --name TalkerBox --add-data "../sounds;sounds" --add-data "../ads.json;." --add-data "hotkey_listener.py;." main.py
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
echo.
pause
