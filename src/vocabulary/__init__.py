# -*- coding: utf-8 -*-
"""Пользовательский словарь Talker Box.

Буст слов при распознавании (hotwords) и замены текста после распознавания.
Формат словарей и план: docs/vocabulary_module_plan.md
"""
from .manager import VocabularyManager

__all__ = ["VocabularyManager"]
