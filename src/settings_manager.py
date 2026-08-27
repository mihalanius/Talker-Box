import json
import os

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.json")

DEFAULT_SETTINGS = {
    "hotkey": "ctrl+win",
    "mode": "toggle",
    "auto_send": False,
    "active_model": "GigaAM v3",
    "models": [
        {
            "name": "GigaAM v3",
            "path": "",
            "type": "sherpa-onnx",
            "language": "ru",
            "size": "215 MB"
        }
    ],
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

    def add_model(self, model):
        self.settings["models"].append(model)
        self.save()

    def remove_model(self, name):
        self.settings["models"] = [m for m in self.settings["models"] if m["name"] != name]
        self.save()
