# -*- coding: utf-8 -*-
"""Управление пользовательским словарём.

Формат — ОДНО правильное слово и СКОЛЬКО УГОДНО неправильных вариантов модели:

    Seed - SID, Sid, Сид, сид, сит, Сит
    Git (Гит) - Гид

Источники слов:
1. `vocabularies/Словарь.txt` — быстрая правка в блокноте (перечитывается каждый раз);
2. JSON-словари в `vocabularies/` (формат см. docs/vocabulary_module_plan.md).

Что делает словарь:
- замены: любой неправильный вариант в тексте автоматически становится правильным словом;
- буст (hotwords): правильные слова передаются модели, чтобы она писала их сразу.
"""
import json
import os
import re

from paths import get_exe_dir
from settings_manager import SettingsManager

CUSTOM_FILE = "custom"             # JSON-файл для новых слов пользователя
TEXT_FILE = "Словарь.txt"          # текстовый словарь для правки в блокноте
HOTWORDS_FILE = "hotwords_cache.txt"


def _clean_target(text):
    """Правильное слово без подсказки произношения: 'Git (Гит)' → 'Git'."""
    text = (text or "").strip()
    text = re.sub(r"\s*\([^()]*\)\s*$", "", text)   # убираем хвостовое (...)
    return text.strip()


class VocabularyManager:
    """Словари: загрузка, замены, буст (hotwords), добавление слов."""

    def __init__(self, vocab_dir=None, settings=None):
        self.vocab_dir = vocab_dir or os.path.join(get_exe_dir(), "vocabularies")
        self.settings = settings if settings is not None else SettingsManager()
        self.hotwords_path = os.path.join(get_exe_dir(), HOTWORDS_FILE)

    # ---------- настройки (settings.json → "vocabulary") ----------

    def _conf(self, key, default):
        conf = self.settings.get("vocabulary", {}) or {}
        return conf.get(key, default)

    @property
    def enabled(self):
        return bool(self._conf("enabled", True))

    @property
    def boost_enabled(self):
        """Буст слов в самой модели — экспериментально, по умолчанию ВЫКЛ.

        Лечим слова заменами после распознавания — это надёжно и без искажений.
        """
        return bool(self._conf("hotwords", False))

    @property
    def hotwords_score(self):
        try:
            return float(self._conf("hotwords_score", 2.0))
        except Exception:
            return 2.0

    @property
    def active_categories(self):
        cats = self._conf("active_categories", [])
        return list(cats) if cats else None

    # ---------- загрузка слов ----------

    def load(self):
        """Нормализованные записи: {правильное слово: {"target", "variants", "score"}}."""
        entries = {}

        def put(target, variants, score):
            t = _clean_target(target)
            if not t:
                return
            e = entries.setdefault(t, {"target": t, "variants": [], "score": score})
            for v in variants:
                v = (v or "").strip()
                if v and v not in e["variants"]:
                    e["variants"].append(v)

        # 1) JSON-словари (старый и новый формат)
        for name in self.list_files():
            data = self._read(name)
            if not data:
                continue
            for cat, cat_data in (data.get("categories") or {}).items():
                if self.active_categories is not None and cat not in self.active_categories:
                    continue
                if not isinstance(cat_data, dict):
                    continue
                for key, value in (cat_data.get("words") or {}).items():
                    if isinstance(value, dict):
                        score = value.get("score", 2.0)
                        if value.get("variants") is not None:
                            put(value.get("target") or key, value.get("variants") or [], score)
                        else:
                            put(value.get("target") or key, [key], score)   # старый формат
                    else:
                        put(value, [key], 2.0)

        # 2) текстовый файл — правится руками, перечитывается всегда
        for entry in self.load_text().values():
            put(entry["target"], entry["variants"], entry.get("score", 2.5))

        return entries

    def list_files(self):
        try:
            return sorted(f[:-5] for f in os.listdir(self.vocab_dir)
                          if f.lower().endswith(".json"))
        except Exception:
            return []

    def _read(self, name):
        try:
            with open(os.path.join(self.vocab_dir, name + ".json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _write(self, name, data):
        os.makedirs(self.vocab_dir, exist_ok=True)
        with open(os.path.join(self.vocab_dir, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ---------- текстовый словарь (правка в блокноте) ----------

    @property
    def text_path(self):
        return os.path.join(self.vocab_dir, TEXT_FILE)

    def _text_files(self):
        """Все .txt в папке словаря — любой файл подхватывается сам (это и есть импорт)."""
        try:
            return sorted(f for f in os.listdir(self.vocab_dir) if f.lower().endswith(".txt"))
        except Exception:
            return []

    def load_text(self):
        """Слова из всех текстовых файлов: 'Правильное - вариант1, вариант2'.

        Любой .txt, положенный в папку vocabularies/, читается автоматически.
        Экспорт — просто скопировать файл кому-то.
        """
        entries = {}
        for name in self._text_files():
            try:
                # utf-8-sig: файлы от любого блокнота чисты, даже с меткой BOM
                with open(os.path.join(self.vocab_dir, name), "r", encoding="utf-8-sig") as f:
                    lines = f.readlines()
            except Exception:
                continue
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = re.split(r"\s+[-–—]\s+", line, maxsplit=1)   # первое " - " = разделитель
                if len(parts) != 2:
                    continue
                target = _clean_target(parts[0])
                variants = [v.strip(" \t()") for v in re.split(r"[,;]", parts[1])]
                if not target:
                    continue
                e = entries.setdefault(target, {"target": target, "variants": [], "score": 2.5})
                for v in variants:
                    if v and v not in e["variants"]:
                        e["variants"].append(v)
        return entries

    # ---------- замены (исправление текста) ----------

    def replacements(self):
        """Замены {неправильный вариант (нижний регистр): правильное слово}."""
        out = {}
        for e in self.load().values():
            t = e["target"]
            for v in e["variants"]:
                out[v.lower()] = t
        return out

    # ---------- hotwords (буст для модели) ----------

    def build_hotwords_file(self):
        """Собрать hotwords-файл (правильные слова); None — если слов нет/словарь выключен."""
        if not self.enabled:
            return None
        entries = self.load()
        if not entries:
            return None
        with open(self.hotwords_path, "w", encoding="utf-8") as f:
            # без комментариев: каждая строка — фраза, иначе модель примет её за слово
            for e in entries.values():
                target = e["target"].strip()
                if target:
                    f.write(f"{target}:{e.get('score', 2.0)}\n")
        return self.hotwords_path

    # ---------- правки словаря ----------

    def add_word(self, target, variants, score=2.5, auto=False):
        """Добавить слово: строка дописывается в конец личного файла словаря.

        Строкой вида: 'Правильное - неправильный1, неправильный2'
        Файл сразу видно в Блокноте — никаких скрытых хранилищ.
        """
        target = _clean_target(target)
        if isinstance(variants, str):
            variants = [variants]        # одно слово можно передать просто строкой
        variants = [v.strip() for v in (variants or []) if v and v.strip()]
        if not target:
            return False
        try:
            os.makedirs(self.vocab_dir, exist_ok=True)
            with open(self.text_path, "a", encoding="utf-8") as f:
                f.write(f"{target} - {', '.join(variants)}\n")
        except Exception:
            return False
        self.build_hotwords_file()
        return True

    def remove_word(self, target, category=None):
        """Удалить слово из JSON-словарей. Возвращает True, если слово было."""
        target = _clean_target(target)
        removed = False
        for name in self.list_files():
            data = self._read(name)
            if not data:
                continue
            changed = False
            for cat, cat_data in (data.get("categories") or {}).items():
                if category and cat != category:
                    continue
                words = cat_data.get("words") if isinstance(cat_data, dict) else None
                if isinstance(words, dict) and target in words:
                    del words[target]
                    changed = True
                    removed = True
            if changed:
                self._write(name, data)
        if removed:
            self.build_hotwords_file()
        return removed
