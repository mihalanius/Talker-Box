import os
import json
import time
import urllib.request
from datetime import datetime

from paths import get_exe_dir

ADS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ads.json")
# кэш баннеров: расширение Quick Bar кладёт ads.json рядом с собой, программа —
# в профиль пользователя, чтобы работало и когда папка программы только для чтения
CACHE_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "TalkerBox")
CACHE_FILE = os.path.join(CACHE_DIR, "ads_cache.json")

DEFAULT_ADS = {
    "enabled": False,
    "interval_minutes": 60,
    "mode": "banner_only",
    "ads_url": "",          # пусто — берём локальный ads.json рядом с программой
    "refresh_minutes": 180,  # как часто перечитывать ads.json с сервера
    "banner": {
        "image": "assets/ads/banner.png",
        "link": "https://your-link.com",
        "alt_text": "Talker Box Pro"
    }
}

class AdManager:
    def __init__(self):
        self.config = DEFAULT_ADS.copy()
        self.last_show_time = 0
        self._rotation = 0          # какой баннер показывать следующим
        self._last_refresh = 0.0
        self.load()

    # ---------- получение списка баннеров ----------
    def ads_source(self):
        """Откуда брать ads.json: сервер (ads_url) или локальный файл."""
        url = str(self.config.get("ads_url") or "").strip()
        return url

    def _read_json(self, path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            return None

    def refresh(self, force=False):
        """Перечитать ads.json (с сервера или локально). True — если данные обновились."""
        interval = float(self.config.get("refresh_minutes", 180)) * 60
        if not force and (time.time() - self._last_refresh) < interval:
            return False
        self._last_refresh = time.time()
        data = None
        url = self.ads_source()
        if url:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "TalkerBox"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
            except Exception:
                data = self._read_json(CACHE_FILE)      # нет сети — берём кэш
        else:
            local = os.path.join(get_exe_dir(), "ads.json")
            data = self._read_json(local) or self._read_json(ADS_FILE) or self._read_json(CACHE_FILE)
        if not isinstance(data, dict):
            return False
        # формат Quick Bar: {"bar": [...], "wide": [...]}; старый формат: {"banner": {...}}
        if "bar" in data or "wide" in data:
            self.config["sets"] = {
                "bar": list(data.get("bar") or []),
                "wide": list(data.get("wide") or []),
            }
            return True
        return False

    def has_ads(self):
        sets = self.config.get("sets") or {}
        return bool(sets.get("bar") or sets.get("wide"))

    def next_ad(self, mode="bar"):
        """Следующий баннер для полоски (по кругу)."""
        sets = self.config.get("sets") or {}
        items = list(sets.get(mode) or sets.get("wide") or sets.get("bar") or [])
        if not items:
            return None
        ad = items[self._rotation % len(items)]
        self._rotation += 1
        if isinstance(ad, dict) and not ad.get("link"):
            # без ссылки баннер не показываем — ищем следующий с ссылкой
            for shift in range(1, len(items) + 1):
                cand = items[(self._rotation + shift) % len(items)]
                if isinstance(cand, dict) and cand.get("link"):
                    return cand
            return None
        return ad if isinstance(ad, dict) else None


    def load(self):
        if os.path.exists(ADS_FILE):
            try:
                with open(ADS_FILE, "r", encoding="utf-8-sig") as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
            except:
                pass

    def save(self):
        with open(ADS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def is_enabled(self):
        return self.config.get("enabled", False)

    def get_mode(self):
        return self.config.get("mode", "banner_only")

    def show_banner(self):
        return self.is_enabled() and self.get_mode() in ("banner_only", "banner_and_tray")

    def get_banner_config(self):
        return self.config.get("banner", {})

    def get_banner_image_path(self):
        banner = self.config.get("banner", {})
        img = banner.get("image", "")
        if img:
            full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), img)
            if os.path.exists(full_path):
                return full_path
        return None

