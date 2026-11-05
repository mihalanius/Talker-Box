# -*- coding: utf-8 -*-
"""Лицензии и пробный период Talker Box.

Модель:
  trial  — 14 дней с полным набором функций и без рекламы;
  free   — после триала: распознавание работает, словарь/история/облачко закрыты,
           внизу показывается реклама;
  pro    — лицензионный ключ: всё открыто, рекламы нет.

Дата первого запуска хранится в трёх местах (settings.json, реестр HKCU, файл в
%APPDATA%), чтобы её нельзя было сбросить переустановкой или правкой одного файла.
Если системные часы «уехали» назад — считаем срок по максимальной замеченной дате.
"""
import json
import os
import re
from datetime import date, datetime, timedelta

TRIAL_DAYS = 14
# Пока приложение не распространяется — лицензирование ОТКЛЮЧЕНО:
# все функции открыты, рекламы нет, триал не тикает.
# Включить продажи: поставить в True — и триал/замки/реклама заработают.
LICENSING_ENABLED = False
CLOCK_ROLLBACK_LIMIT_DAYS = 1
REG_PATH = r"Software\TalkerBox"
MARKER_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "TalkerBox")
MARKER_FILE = os.path.join(MARKER_DIR, "license.dat")

KEY_RE = re.compile(r"^TB-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")

FEATURES_PRO = ("dictionary", "history", "cloud")


def _today():
    return date.today()


class License:
    def __init__(self, settings):
        self.settings = settings
        self.clock_rollback = False
        self.first_run = None
        self.last_seen = None
        self.key = ""
        self.note_launch()

    # ---------- чтение/запись дат в три места ----------
    def _from_settings(self):
        return (self.settings.get("lic_first_run", "") or "",
                self.settings.get("lic_last_seen", "") or "",
                self.settings.get("lic_key", "") or "")

    def _from_registry(self):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH) as k:
                first = winreg.QueryValueEx(k, "FirstRun")[0]
                last = winreg.QueryValueEx(k, "LastSeen")[0]
                key = winreg.QueryValueEx(k, "Key")[0] if _has_value(k, "Key") else ""
                return (str(first), str(last), str(key))
        except Exception:
            return ("", "", "")

    def _from_marker(self):
        try:
            with open(MARKER_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            return (str(d.get("first_run", "")), str(d.get("last_seen", "")),
                    str(d.get("key", "")))
        except Exception:
            return ("", "", "")

    def _write_all(self, first, last, key):
        self.settings.set("lic_first_run", first)
        self.settings.set("lic_last_seen", last)
        self.settings.set("lic_key", key)
        try:
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH) as k:
                winreg.SetValueEx(k, "FirstRun", 0, winreg.REG_SZ, first)
                winreg.SetValueEx(k, "LastSeen", 0, winreg.REG_SZ, last)
                winreg.SetValueEx(k, "Key", 0, winreg.REG_SZ, key)
        except Exception:
            pass
        try:
            os.makedirs(MARKER_DIR, exist_ok=True)
            with open(MARKER_FILE, "w", encoding="utf-8") as f:
                json.dump({"first_run": first, "last_seen": last, "key": key}, f)
        except Exception:
            pass

    # ---------- запуск ----------
    def note_launch(self):
        """Зафиксировать запуск: обновить дату «последнего визита», при первом — старт триала."""
        sources = [self._from_settings(), self._from_registry(), self._from_marker()]
        firsts = [s[0] for s in sources if s[0]]
        lasts = [s[1] for s in sources if s[1]]
        keys = [s[2] for s in sources if s[2]]

        today = _today().isoformat()
        first = min(firsts) if firsts else today
        last = max(lasts) if lasts else today
        key = keys[0] if keys else ""

        # часы назад: сегодняшняя дата меньше последней замеченной
        try:
            if _today() < datetime.fromisoformat(last).date() - timedelta(days=CLOCK_ROLLBACK_LIMIT_DAYS):
                self.clock_rollback = True
                last = max(last, today)          # не даём «отмотать» срок
        except Exception:
            pass

        self.first_run, self.last_seen, self.key = first, last, key
        self._write_all(first, max(last, today), key)

    # ---------- состояние ----------
    def is_pro(self):
        return bool(self.key) and bool(KEY_RE.match(self.key.strip().upper())) or \
            bool(self.settings.get("lic_pro", False))

    def days_left(self):
        try:
            start = datetime.fromisoformat(self.first_run).date()
        except Exception:
            return TRIAL_DAYS
        end = start + timedelta(days=TRIAL_DAYS)
        return max(0, (end - _today()).days)

    def mode(self):
        if not LICENSING_ENABLED:
            return "pro"          # лицензирование выключено — всё открыто
        if self.is_pro():
            return "pro"
        return "trial" if self.days_left() > 0 else "free"

    def can(self, feature):
        """Доступ к функции: словарь / история / облачко."""
        if feature in FEATURES_PRO:
            return self.mode() in ("trial", "pro")
        return True

    def show_ads(self):
        return self.mode() == "free"

    def status_text(self):
        m = self.mode()
        if not LICENSING_ENABLED:
            return "Лицензирование отключено — все функции открыты"
        if m == "pro":
            return "Лицензия активирована — все функции открыты"
        if m == "trial":
            return f"Пробный период: осталось {self.days_left()} дн. — все функции открыты"
        return "Бесплатная версия: словарь, история и облачко доступны в Pro"

    # ---------- активация ----------
    def activate(self, key):
        """Принять ключ. Пока проверяем только формат; подпись добавим с сервером."""
        key = (key or "").strip().upper()
        if not KEY_RE.match(key):
            return False, "Ключ должен быть вида TB-XXXX-XXXX-XXXX"
        self.key = key
        self._write_all(self.first_run or _today().isoformat(),
                        self.last_seen or _today().isoformat(), key)
        return True, "Лицензия активирована"


def _has_value(key, name):
    try:
        import winreg
        winreg.QueryValueEx(key, name)
        return True
    except Exception:
        return False
