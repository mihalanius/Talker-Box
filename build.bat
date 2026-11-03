@echo off
cd /d "%~dp0"

echo ========================================
echo Talker Box - Build Script
echo ========================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first!
    pause
    exit /b 1
)

echo [1/5] Installing build dependencies...
venv\Scripts\python.exe -m pip install pyinstaller

echo.
echo [2/5] Building executable...
cd src
if exist dist rmdir /S /Q dist
if exist build rmdir /S /Q build
..\venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name TalkerBox --icon="../talker_box.ico" --add-data "../sounds;sounds" --add-data "../fonts;fonts" --add-data "../ads.json;." --add-data "hotkey_listener.py;." --add-data "../talker_box.png;." --add-data "../mascot.png;." --add-data "../mascot_new.png;." --add-data "../help.html;." main.py
cd ..

echo.
echo [3/5] Copying files...
mkdir dist\TalkerBox 2>nul
copy src\dist\TalkerBox.exe dist\TalkerBox\
copy ads.json dist\TalkerBox\
xcopy /E /I /Y sounds dist\TalkerBox\sounds
xcopy /E /I /Y fonts dist\TalkerBox\fonts
copy talker_box.png dist\TalkerBox\
copy mascot.png dist\TalkerBox\
if exist "mascot_new.png" copy mascot_new.png dist\TalkerBox\
copy help.html dist\TalkerBox\
if exist "settings.json" copy settings.json dist\TalkerBox\
if exist "vocabularies" xcopy /E /I /Y vocabularies dist\TalkerBox\vocabularies

echo.
echo [4/5] Copying GigaAM model...
if not exist "models\GigaAM\encoder.int8.onnx" (
    echo ERROR: model not found in "%~dp0models\GigaAM"
    pause
    exit /b 1
)
mkdir dist\TalkerBox\models\GigaAM 2>nul
xcopy /E /I /Y "models\GigaAM" dist\TalkerBox\models\GigaAM

echo.
echo [5/5] Done!
echo.
echo Executable: dist\TalkerBox\TalkerBox.exe
echo Now open installer\talkerbox.iss in Inno Setup and click Compile
echo.
pause
