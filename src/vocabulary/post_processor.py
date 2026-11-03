# -*- coding: utf-8 -*-
"""Пост-обработка распознанного текста: замена неправильных слов по словарю.

Модель пишет «Гид» → в текст встаёт «Git». Замена — по целым словам,
без учёта регистра, длинные варианты подставляются первыми.

Варианты бывают двух видов:
- обычные:   `Git - Гид, Гит`            — точное совпадение;
- маски:     `Time Web - ~тайм*`         — звёздочка = любые буквы,
             ловит «Таймвел», «Таймвеб», «Тайм-эп» и подобное разом.
"""
import re


class PostProcessor:
    def __init__(self, manager):
        self.manager = manager

    def process(self, text):
        """Применить замены словаря к тексту."""
        if not text:
            return text
        try:
            reps = self.manager.replacements()
        except Exception:
            return text
        if not reps:
            return text

        exact = {k: v for k, v in reps.items() if not self._is_mask(k)}
        masks = {k: v for k, v in reps.items() if self._is_mask(k)}

        # 1) точные варианты — сначала они: они конкретнее масок
        #    (иначе маска съест половину слова, и точное правило не сработает)
        if exact:
            keys = sorted(exact.keys(), key=len, reverse=True)
            pattern = re.compile(
                r"(?<!\w)(?:" + "|".join(re.escape(k) for k in keys) + r")(?!\w)",
                re.IGNORECASE)
            text = pattern.sub(lambda m: exact.get(m.group(0).lower(), m.group(0)), text)

        # 2) маски (гибкие шаблоны) — добирают всё, что точные пропустили
        if masks:
            keys = sorted(masks.keys(), key=len, reverse=True)
            body = "|".join(f"({self._to_regex(k)})" for k in keys)
            pattern = re.compile(r"(?<!\w)(?:" + body + r")(?!\w)", re.IGNORECASE)

            def _rep(m):
                for i, k in enumerate(keys, start=1):
                    if m.group(i):
                        return masks[k]
                return m.group(0)

            text = pattern.sub(_rep, text)

        return text

    @staticmethod
    def _is_mask(key):
        """Маска — строка с ~ в начале или со звёздочкой внутри."""
        return key.startswith("~") or "*" in key

    @staticmethod
    def _to_regex(key):
        """Маска в регулярное выражение: * — любые буквы/цифры/дефис."""
        esc = re.escape(key.lstrip("~"))
        return esc.replace(r"\*", r"[\w\-]*")
