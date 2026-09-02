import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
font = app.font()
font.setFamily("Segoe UI")
font.setPointSize(10)
app.setFont(font)

print("1. Imports...")
from settings_manager import SettingsManager
print("   SettingsManager OK")
from recorder import Recorder
print("   Recorder OK")
from ad_manager import AdManager
print("   AdManager OK")
from sounds import play_start_sound, play_stop_sound
print("   Sounds OK")
from waveform import WaveformWindow
print("   Waveform OK")
from transcriber import Transcriber
print("   Transcriber OK")

print("2. Creating SettingsManager...")
settings = SettingsManager()
print(f"   mode={settings.get('mode')}, hotkey={settings.get('hotkey')}")

print("3. Creating Recorder...")
recorder = Recorder()
print("   Recorder OK")

print("4. Creating AdManager...")
ad_manager = AdManager()
print("   AdManager OK")

print("5. Testing keyboard import...")
try:
    import keyboard
    print("   keyboard OK")
except Exception as e:
    print(f"   keyboard FAIL: {e}")

print("6. Testing pyperclip import...")
try:
    import pyperclip
    print("   pyperclip OK")
except Exception as e:
    print(f"   pyperclip FAIL: {e}")

print("7. Testing main window creation...")
try:
    from main import MainWindow
    window = MainWindow()
    window.show()
    print("   MainWindow OK")
except Exception as e:
    import traceback
    traceback.print_exc()

print("DONE")
QTimer.singleShot(3000, app.quit)
app.exec()
