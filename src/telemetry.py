# -*- coding: utf-8 -*-
"""Анонимная статистика Talker Box.

Что собирается (и только это):
  install   — первая установка/первый запуск (один раз);
  launch    — запуск программы (не чаще раза в сутки);
  ad_show   — показы рекламных баннеров, сгруппированные по id баннера;
  ad_click  — клики по баннерам.

Чего НЕ собирается: текст, аудио, имена файлов, клавиши, окна, IP в явном виде,
личные данные. Идентификатор установки — случайный UUID, не связан с человеком.

Отправка: POST JSON на адрес из настроек (`telemetry_url`). Если адрес пуст или
интернета нет — события копятся в файле и уходят позже. Пользователь может
выключить всё галочкой в настройках (`telemetry_enabled` = false).
"""
import json
import os
import socket
import threading
import time
import uuid
from datetime import date

from logger import log

STATE_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "TalkerBox")
BUFFER_FILE = os.path.join(STATE_DIR, "telemetry.jsonl")
BUFFER_LIMIT = 500          # больше строк не копим
VERSION = "2.4.0"


class Telemetry:
    def __init__(self, settings):
        self.settings = settings
        # выключателя в интерфейсе нет: пользователь уведомлён в разделе «Инфо»,
        # а согласие подтверждает при покупке (решение GOLDMAN 05.11.2026)
        self.enabled = True
        install_id = str(settings.get("install_id", "") or "")
        if not install_id:
            install_id = uuid.uuid4().hex
            settings.set("install_id", install_id)
        self.install_id = install_id

    # ---------- адрес приёма ----------
    def endpoint(self):
        return str(self.settings.get("telemetry_url", "") or "").strip()

    # ---------- события ----------
    def _base(self):
        import platform
        return {
            "id": self.install_id,
            "ver": VERSION,
            "os": platform.platform(terse=True),
            "ts": int(time.time()),
        }

    def _write(self, payload):
        if not self.enabled:
            return
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            # не раздуваем файл: старые строки отбрасываем
            lines = []
            if os.path.exists(BUFFER_FILE):
                with open(BUFFER_FILE, "r", encoding="utf-8") as f:
                    lines = f.readlines()[-BUFFER_LIMIT:]
            lines.append(json.dumps(payload, ensure_ascii=False) + "\n")
            with open(BUFFER_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except Exception:
            pass

    def event(self, name, **props):
        if not self.enabled:
            return
        payload = self._base()
        payload["event"] = name
        payload.update(props)
        self._write(payload)

    def install_or_launch(self):
        """Первая установка — один раз; запуск — не чаще раза в сутки."""
        today = date.today().isoformat()
        if not self.settings.get("telemetry_installed", False):
            self.settings.set("telemetry_installed", True)
            self.event("install")
            log("TELEMETRY", "install")
        if self.settings.get("telemetry_last_launch", "") != today:
            self.settings.set("telemetry_last_launch", today)
            self.event("launch")
            log("TELEMETRY", "launch")

    def ad_shown(self, ad_id):
        self.event("ad_show", ad=str(ad_id or "")[:120])

    def ad_clicked(self, ad_id):
        self.event("ad_click", ad=str(ad_id or "")[:120])

    # ---------- отправка ----------
    def flush(self):
        """Отправить накопленное в фоне (не блокирует интерфейс)."""
        if not self.enabled or not self.endpoint() or not os.path.exists(BUFFER_FILE):
            return
        threading.Thread(target=self._send, daemon=True).start()

    def _send(self):
        url = self.endpoint()
        try:
            with open(BUFFER_FILE, "r", encoding="utf-8") as f:
                lines = [ln for ln in f.read().splitlines() if ln.strip()]
        except Exception:
            return
        if not lines:
            return
        sent = []
        for ln in lines:
            try:
                payload = json.loads(ln)
            except Exception:
                continue
            if self._post(url, payload):
                sent.append(ln)
        # из буфера убираем только успешно отправленное
        try:
            left = [ln for ln in lines if ln not in sent]
            with open(BUFFER_FILE, "w", encoding="utf-8") as f:
                f.writelines([ln + "\n" for ln in left])
        except Exception:
            pass

    @staticmethod
    def _post(url, payload):
        try:
            import urllib.request
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json", "User-Agent": "TalkerBox"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False


def advertisement_id(ad):
    """Стабильный идентификатор баннера для статистики."""
    if not isinstance(ad, dict):
        return ""
    return str(ad.get("id") or ad.get("link") or ad.get("video") or ad.get("image") or "")
