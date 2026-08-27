import os
import json
import time
from datetime import datetime

ADS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ads.json")

DEFAULT_ADS = {
    "enabled": False,
    "interval_minutes": 60,
    "banner": {
        "image": "assets/ads/banner.png",
        "link": "https://your-link.com",
        "alt_text": "Talker Box Pro"
    },
    "tray_notification": {
        "title": "Talker Box",
        "message": "Попробуйте Talker Box Pro — 50+ языков",
        "link": "https://your-link.com"
    }
}

class AdManager:
    def __init__(self):
        self.config = DEFAULT_ADS.copy()
        self.last_show_time = 0
        self.load()

    def load(self):
        if os.path.exists(ADS_FILE):
            try:
                with open(ADS_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
            except:
                pass

    def save(self):
        with open(ADS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def is_enabled(self):
        return self.config.get("enabled", False)

    def should_show(self):
        if not self.is_enabled():
            return False
        interval = self.config.get("interval_minutes", 60) * 60
        return (time.time() - self.last_show_time) >= interval

    def mark_shown(self):
        self.last_show_time = time.time()

    def get_banner_config(self):
        return self.config.get("banner", {})

    def get_tray_config(self):
        return self.config.get("tray_notification", {})

    def get_banner_image_path(self):
        banner = self.config.get("banner", {})
        img = banner.get("image", "")
        if img:
            full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), img)
            if os.path.exists(full_path):
                return full_path
        return None

    def set_enabled(self, enabled):
        self.config["enabled"] = enabled
        self.save()

    def set_interval(self, minutes):
        self.config["interval_minutes"] = minutes
        self.save()

    def set_banner(self, image_path=None, link=None, alt_text=None):
        banner = self.config.get("banner", {})
        if image_path:
            banner["image"] = image_path
        if link:
            banner["link"] = link
        if alt_text:
            banner["alt_text"] = alt_text
        self.config["banner"] = banner
        self.save()

    def set_tray_notification(self, title=None, message=None, link=None):
        tray = self.config.get("tray_notification", {})
        if title:
            tray["title"] = title
        if message:
            tray["message"] = message
        if link:
            tray["link"] = link
        self.config["tray_notification"] = tray
        self.save()
