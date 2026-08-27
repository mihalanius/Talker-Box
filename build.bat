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
pyinstaller --onefile --windowed --name TalkerBox --icon=../assets/talkerbox.ico --add-data "../assets;assets" --add-data "../ads.json;." main.py
cd ..

echo.
echo [3/4] Copying files...
mkdir dist\TalkerBox 2>nul
copy dist\TalkerBox\TalkerBox.exe dist\TalkerBox\
copy ads.json dist\TalkerBox\
xcopy /E /I /Y assets dist\TalkerBox\assets

echo.
echo [4/4] Done!
echo.
echo Executable: dist\TalkerBox\TalkerBox.exe
echo.
pause
