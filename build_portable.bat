@echo off
rem ============================================================
rem  Talker Box - PORTABLE build
rem  Result: portable\Talker Box Portable\  (+ zip for transfer)
rem  Folder is self-contained: exe + model + dictionaries.
rem ============================================================
cd /d "%~dp0"
chcp 65001 >nul
setlocal

set "VERSION=2.3.6"
set "OUT=portable\Talker Box Portable"
set "ZIP=portable\TalkerBox-Portable-v%VERSION%.zip"

echo ========================================
echo  Talker Box - Portable build
echo ========================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first!
    pause
    exit /b 1
)

echo [1/5] Installing build dependencies...
venv\Scripts\python.exe -m pip install pyinstaller
if errorlevel 1 goto :fail

echo.
echo [2/5] Building executable...
cd src
if exist dist rmdir /S /Q dist
if exist build rmdir /S /Q build
..\venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name TalkerBox --icon="../talker_box.ico" --add-data "../sounds;sounds" --add-data "../fonts;fonts" --add-data "../images;images" --add-data "../lang;lang" --add-data "../ads.json;." --add-data "hotkey_listener.py;." --add-data "../talker_box.png;." --add-data "../mascot_new.png;." --add-data "../help.html;." main.py
if errorlevel 1 goto :fail
cd ..

echo.
echo [3/5] Collecting portable folder...
if exist "portable" rmdir /S /Q "portable"
mkdir "%OUT%"
copy /Y "src\dist\TalkerBox.exe" "%OUT%\TalkerBox.exe" >nul
copy /Y ads.json "%OUT%\" >nul
xcopy /E /I /Y sounds "%OUT%\sounds" >nul
xcopy /E /I /Y fonts "%OUT%\fonts" >nul
xcopy /E /I /Y images "%OUT%\images" >nul
copy /Y talker_box.png "%OUT%\" >nul
if exist "mascot_new.png" copy /Y mascot_new.png "%OUT%\" >nul
copy /Y help.html "%OUT%\" >nul
if exist "settings.json" copy /Y settings.json "%OUT%\" >nul
if exist "vocabularies" xcopy /E /I /Y vocabularies "%OUT%\vocabularies" >nul

echo.
echo [4/5] Copying GigaAM model...
if not exist "models\GigaAM\encoder.int8.onnx" (
    echo ERROR: model not found in "%~dp0models\GigaAM"
    goto :fail
)
mkdir "%OUT%\models\GigaAM" 2>nul
xcopy /E /I /Y "models\GigaAM" "%OUT%\models\GigaAM" >nul
copy /Y "portable_readme.txt" "%OUT%\ПРОЧТИ МЕНЯ.txt" >nul

echo.
echo [5/5] Packing ZIP...
if exist "%ZIP%" del /Q "%ZIP%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%OUT%\*' -DestinationPath '%ZIP%' -Force"
if errorlevel 1 (
    echo WARNING: ZIP not created ^(folder is ready anyway^)
)

echo.
echo ========================================
echo  Done!
echo  Folder: %OUT%
echo  ZIP   : %ZIP%
echo ========================================
echo.
pause
exit /b 0

:fail
echo.
echo BUILD FAILED
pause
exit /b 1
