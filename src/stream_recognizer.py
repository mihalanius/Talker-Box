# -*- coding: utf-8 -*-
"""Живое распознавание (Talker Box Стриминг) — текст появляется по мере речи.

Принцип работы (только GigaAM, других моделей нет):
- микрофон слушается постоянно;
- во время речи каждые ~0.4 сек текущий кусочек прогоняется через GigaAM —
  и в облачко ПОСЛОВНО попадают уже узнанные слова (быстрая отрисовка);
- когда человек замолчал (пауза ~0.45 сек) — фраза прогоняется начисто,
  и возвращается точный итоговый текст фразы.
"""
import threading
import time

import numpy as np

from logger import log

SAMPLE_RATE = 16000


class PhraseStream:
    """Собирает микрофонный поток в фразы и показывает текст по мере речи."""

    def __init__(self, transcriber, on_phrase, silence_thresh=0.007,
                 pause_sec=0.45, max_phrase_sec=18, partial_every=0.4):
        self.transcriber = transcriber
        self.on_phrase = on_phrase            # callback(text, is_partial)
        self.silence_thresh = silence_thresh  # порог тишины (0..1)
        self.pause_sec = pause_sec            # пауза = конец фразы
        self.max_phrase_sec = max_phrase_sec  # слишком длинную фразу делим
        self.partial_every = partial_every    # как часто перерисовывать слова
        self._busy = False                    # идёт распознавание кусочка
        self.last_level = 0.0                 # уровень сигнала (для анимации волны)
        self.reset()

    def reset(self):
        self._chunks = []
        self._samples = 0
        self._speech = False
        self._silence = 0.0
        self._last_partial = 0.0

    @property
    def is_speech(self):
        """Идёт ли сейчас речь (для волны в облачке)."""
        return self._speech

    def start(self):
        self.reset()
        log("PHRASE_STREAM", "started")

    def feed(self, chunk):
        """Сюда приходят кусочки микрофона (numpy int16, форма (N, 1))."""
        try:
            if chunk is None or len(chunk) == 0:
                return
            data = chunk.flatten()
            level = float(np.abs(data).mean()) / 32768.0
            self.last_level = level
            dur = len(data) / SAMPLE_RATE

            if level >= self.silence_thresh:
                if not self._speech:
                    self._speech = True
                    log("PHRASE_SPEECH", f"level={level:.4f}")
                self._silence = 0.0
                self._chunks.append(data)
                self._samples += len(data)
                # быстрая отрисовка: показываем, что уже услышали
                now = time.monotonic()
                if (not self._busy) and (now - self._last_partial) >= self.partial_every:
                    self._last_partial = now
                    audio = np.concatenate(self._chunks, axis=0)
                    threading.Thread(target=self._recognize, args=(audio, True), daemon=True).start()
                if self._samples >= int(self.max_phrase_sec * SAMPLE_RATE):
                    self._finish()
            else:
                if self._speech:
                    self._chunks.append(data)
                    self._samples += len(data)
                    self._silence += dur
                    if self._silence >= self.pause_sec:
                        self._finish()
        except Exception as e:
            log("PHRASE_FEED_ERROR", str(e))

    def _finish(self):
        if not self._chunks:
            self.reset()
            return
        audio = np.concatenate(self._chunks, axis=0)
        self.reset()
        threading.Thread(target=self._recognize, args=(audio, False), daemon=True).start()

    def _recognize(self, audio, is_partial):
        if not is_partial:
            self._busy = True
        try:
            text = self.transcriber.transcribe(audio)
            text = (text or "").strip()
            log("PHRASE_" + ("PARTIAL" if is_partial else "DONE"), f"len={len(text)} text={repr(text[:60])}")
            if text and self.on_phrase:
                self.on_phrase(text, is_partial)
        except Exception as e:
            log("PHRASE_ASR_ERROR", str(e))
        finally:
            if not is_partial:
                self._busy = False
