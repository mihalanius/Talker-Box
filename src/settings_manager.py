import json
import os
from paths import get_exe_dir

SETTINGS_FILE = os.path.join(get_exe_dir(), "settings.json")

BUILTIN_MODEL = {
    "name": "GigaAM v3 trans-punct",
    "path": "models/GigaAM",
    "type": "sherpa-onnx",
    "language": "ru",
    "size": "220 MB"
}

DEFAULT_SETTINGS = {
    "hotkey": "ctrl+win",
    "mode": "hold",
    "auto_send": True,
    "auto_start": True,
    "minimize_to_tray": True
}

class SettingsManager:
    def __init__(self):
        self.settings = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.settings.update(loaded)
                # Очистка устаревших полей (v2.0)
                self.settings.pop("active_model", None)
                self.settings.pop("models", None)
            except:
                pass

    def save(self):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()
