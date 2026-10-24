# -*- coding: utf-8 -*-
"""Плавающее облачко живого текста.

Показывает распознанную речь ПОД (над) активным полем ввода: следует за кареткой
текста, а если каретку найти не удаётся — за курсором мыши. Кликам не мешает
(окно прозрачно для ввода), всегда поверх окон.
"""
import ctypes
import math
import time
from ctypes import wintypes

from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class SendButtonWindow(QWidget):
    """Кнопка «Отправить» — отдельное окно поверх облачка.

    Облачко прозрачно для мыши, а кнопке нужны и клики, и курсор-«рука» —
    поэтому она живёт отдельным окном поверх всего.
    """
    clicked = pyqtSignal()

    def __init__(self):
        super().__init__(None,
                         Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)   # рука с указательным пальцем
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._family = ""
        self._hover = False
        self._size = 13
        self.label = QLabel("[Отправить]")
        self.label.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self.label)
        self.set_style(False)

    def set_style(self, hover):
        """Зелёный текст; на наведении — ярче; шрифт и размер — как у распознанного текста."""
        self._hover = bool(hover)
        color = "#14b89a" if hover else "#2e8b75"
        fam = ("font-family: '%s';" % self._family) if self._family else ""
        self.label.setStyleSheet(
            "QLabel { background: transparent; color: %s; border: none; %s"
            " padding: 0 13px 7px 13px; font-size: %dpx; }"
            % (color, fam, self._size))

    def set_font(self, family, size):
        """Шрифт и размер кнопки — те же, что у распознанного текста в настройках."""
        self._family = (family or "").replace("'", "")
        try:
            self._size = max(8, int(size))
        except Exception:
            self._size = 13
        self.set_style(self._hover)

    def enterEvent(self, e):
        self.set_style(True)          # курсор над кнопкой — текст ярче
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.set_style(False)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()       # клик = второй жм хоткея
        super().mousePressEvent(e)


class WaveBars(QWidget):
    """Волна из капсулы (WaveformWindow._paint_recording) — точная копия:
    та же анимация, те же столбики и цвета, только БЕЗ тёмной подложки."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(208, 36)   # высота — вполовину (по пикам сверху-снизу)
        self.phase = 0.0
        self._active = False          # волна живёт только пока идёт речь
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(33)  # темп анимации — как в капсуле

    def set_active(self, active):
        """Волна играет, когда в микрофон говорят, и гаснет в тишине/отмене."""
        active = bool(active)
        if active == self._active:
            return
        self._active = active
        if active:
            self.phase = 0.0
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        self.phase = 0.0

    def hideEvent(self, e):
        super().hideEvent(e)
        self._active = False
        self._timer.stop()

    def _tick(self):
        self.phase += 0.4            # шаг фазы — как в капсуле
        self.update()

    def paintEvent(self, e):
        if not self._active:         # тишина/отмена — волны не видно
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        n = 20
        bar_w = 3
        gap = (w - 20) / (n - 1)
        sx = 10
        for i in range(n):
            v = math.sin(self.phase + i * 0.45) * 0.7
            v += math.sin(self.phase * 1.8 + i * 0.35) * 0.4
            v += math.sin(self.phase * 0.6 + i * 0.7) * 0.3
            bh = max(2, abs(v) * h * 0.7)
            x = sx + i * gap - bar_w / 2
            y = (h - bh) / 2
            intensity = 100 + int(abs(v) * 155)
            p.setBrush(QColor(0, intensity, 100 + intensity // 3, 220))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(int(x), int(y), bar_w, int(bh), 1, 1)
        p.end()


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
        ("rcCaret", RECT),
    ]


def _caret_pos():
    """Экранная позиция каретки текста активного окна (или None)."""
    try:
        user32 = ctypes.windll.user32
        gti = GUITHREADINFO()
        gti.cbSize = ctypes.sizeof(GUITHREADINFO)
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        tid = user32.GetWindowThreadProcessId(hwnd, None)
        if not user32.GetGUIThreadInfo(tid, ctypes.byref(gti)):
            return None
        if gti.hwndCaret:
            r = gti.rcCaret
            if r.right > r.left and r.bottom > r.top:
                pt = wintypes.POINT(r.left, r.top)
                user32.ClientToScreen(gti.hwndCaret, ctypes.byref(pt))
                return (pt.x, pt.y)
    except Exception:
        pass
    return None


def _cursor_pos():
    try:
        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return (pt.x, pt.y)
    except Exception:
        return None


class StreamOverlay(QWidget):
    def __init__(self):
        super().__init__(None,
                         Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.WindowTransparentForInput |
                         Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.label = QLabel("")
        self.label.setWordWrap(True)       # после предела ширины — текст идёт вниз
        self.label.setMaximumWidth(570)    # предел ширины (как у облачка сообщений)
        self.label.setStyleSheet(
            "QLabel { background: transparent; color: #5c5c5c;"
            " border: none; padding: 9px 13px 2px 13px;"
            " font-size: 12px; line-height: 1.4; }")

        # нижняя строка: время диктовки и крестик сброса
        self.time_label = QLabel("")
        self.time_label.setStyleSheet(
            "QLabel { background: transparent; color: #2e8b75; border: none;"
            " padding: 0 13px 7px 13px; font-size: 12px; }")
        self.close_label = QLabel("✕")
        self.close_label.setStyleSheet(
            "QLabel { background: transparent; color: #2e8b75; border: none;"
            " font-weight: bold; padding: 0 13px 7px 13px; font-size: 13px; }")

        # место под кнопку «Отправить» — слева в нижней строке;
        # сама кнопка живёт отдельным окном поверх (ей нужны клики и курсор-рука)
        self.send_label = QLabel("[Отправить]")
        self.send_label.setStyleSheet(
            "QLabel { background: transparent; color: transparent; border: none;"
            " padding: 0 13px 7px 13px; font-size: 13px; }")
        self.send_button = SendButtonWindow()

        self.box = QWidget()
        self.box.setStyleSheet(
            "QWidget { background: #ececec; border: none; border-radius: 10px; }")
        box_lay = QVBoxLayout(self.box)
        box_lay.setContentsMargins(0, 0, 0, 0)
        box_lay.setSpacing(0)
        box_lay.addWidget(self.label)
        foot = QHBoxLayout()
        foot.setContentsMargins(0, 0, 0, 0)
        self.wave = WaveBars()
        foot.addWidget(self.send_label)  # слева — «Отправить»
        foot.addStretch()
        foot.addWidget(self.wave)   # волна — по центру нижней строки
        foot.addStretch()
        foot.addWidget(self.time_label)
        foot.addWidget(self.close_label)
        box_lay.addLayout(foot)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.box)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._follow)
        self._timer.start(120)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_text(self, text):
        """Показать текст: поле растёт по ширине (до предела), дальше — по высоте."""
        if not getattr(self, "_enabled", True):
            return
        if time.monotonic() < getattr(self, "_flash_until", 0.0):
            return   # после сброса держим «Сброшено» — запоздалый текст не мешает
        text = text or ""
        self.label.setText(text)
        fm = self.label.fontMetrics()
        try:
            tw = fm.horizontalAdvance(text)
        except Exception:
            tw = fm.boundingRect(text).width()
        # минимум 380px — влезают кнопка «Отправить» + волна + время + крестик;
        # дальше облачко растёт за текстом до предела 570
        w = max(380, min(570, tw + 26))
        h = self.label.heightForWidth(w)     # упёрлось в ширину — растёт вниз
        if not h:
            h = fm.height()
        # строгий размер всего облачка: текст + нижняя строка (волна/время/крестик)
        self.setFixedSize(w, h + self.wave.height() + 6)
        self._follow()
        self.show()
        self.raise_()
        self._sync_send_button()
        self._hide_timer.stop()

    def hide_later(self, ms=2500):
        """Скрыть через паузу (после окончания диктовки)."""
        self._hide_timer.start(ms)

    def apply_style(self, bg, fg, font_px, opacity=100, family=""):
        """Настройки облачка: фон, текст, шрифт (размер и название), прозрачность."""
        self._style = (bg, fg, font_px, opacity, family)
        try:
            r, g, b = tuple(int(bg[i:i + 2], 16) for i in (1, 3, 5))
        except Exception:
            r, g, b = 236, 236, 236
        a = max(20, min(100, int(opacity))) / 100.0
        f = QFont()
        if family:
            f.setFamily(family)
        f.setPointSize(max(7, int(font_px) - 3))
        self.label.setFont(f)
        fam = ("font-family: '%s';" % family.replace("'", "")) if family else ""
        # фон с прозрачностью — на самой коробке (иначе под текстом непрозрачная подложка)
        self.box.setStyleSheet(
            "QWidget { background: rgba(%d,%d,%d,%.2f); border: none; border-radius: 10px; }"
            % (r, g, b, a))
        self.label.setStyleSheet(
            "QLabel { background: transparent; color: %s; border: none; %s"
            " padding: 9px 13px 2px 13px; font-size: %dpx; line-height: 1.4; }"
            % (fg, fam, int(font_px)))
        # таймер и кнопка «Отправить» — тем же шрифтом и размером, что и распознанный текст
        self.time_label.setStyleSheet(
            "QLabel { background: transparent; color: #2e8b75; border: none; %s"
            " padding: 0 13px 7px 13px; font-size: %dpx; }" % (fam, int(font_px)))
        self.send_label.setStyleSheet(
            "QLabel { background: transparent; color: transparent; border: none; %s"
            " padding: 0 13px 7px 13px; font-size: %dpx; }" % (fam, int(font_px)))
        self.send_button.set_font(family, font_px)

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        if not self._enabled:
            self.hide()

    def set_time(self, text):
        """Время диктовки в нижней строке облачка."""
        self.time_label.setText(text or "")

    def set_wave_active(self, active):
        """Волна играет, пока идёт речь; в тишине и при отмене — гаснет."""
        self.wave.set_active(active)

    def flash_reset(self, message="Сброшено — жмите хоткей заново"):
        """Красная вспышка: диктовка отменена."""
        self._flash_until = 0.0
        self.show_text(message)
        self._flash_until = time.monotonic() + 2.0   # 2 секунды держим «Сброшено»
        self.box.setStyleSheet(
            "QWidget { background: #f2c9c9; border: none; border-radius: 10px; }")
        self.label.setStyleSheet(
            "QLabel { background: transparent; color: #9c2222; border: none;"
            " padding: 9px 13px 2px 13px; font-size: 12px; }")
        self.set_time("")
        QTimer.singleShot(1200, self._restore_style)
        self._hide_timer.start(2000)   # через 2 секунды облачко исчезает само

    def _restore_style(self):
        st = getattr(self, "_style", None)
        if st:
            self.apply_style(*st)

    def capture_anchor(self):
        """Закрепить облачко у поля ввода (позиция берётся один раз, статично)."""
        self._flash_until = 0.0     # новая диктовка — защита «Сброшено» снимается
        self._anchor = _caret_pos() or _cursor_pos()

    def clear_anchor(self):
        """Отпустить привязку (позиция будет взята заново при следующей диктовке)."""
        self._anchor = None

    def close_rect(self):
        """Прямоугольник крестика в экранных координатах (для распознавания клика)."""
        try:
            p = self.close_label.mapToGlobal(self.close_label.rect().topLeft())
            r = self.close_label.rect()
            return (p.x() - 6, p.y() - 6, r.width() + 12, r.height() + 12)
        except Exception:
            return None

    def set_send_visible(self, visible):
        """Кнопка «Отправить» видна только во время диктовки."""
        self.send_label.setVisible(bool(visible))
        self._sync_send_button()

    def _sync_send_button(self):
        """Кнопка-окно встаёт точно на место метки в нижней строке."""
        if not self.send_label.isVisible() or not self.isVisible():
            self.send_button.hide()
            return
        pos = self.send_label.mapToGlobal(QPoint(0, 0))
        self.send_button.setFixedSize(self.send_label.width(), self.send_label.height())
        self.send_button.move(pos)
        self.send_button.show()
        self.send_button.raise_()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.send_button.hide()   # кнопка живёт вместе с облачком

    def _follow(self):
        if not self.isVisible():
            return
        pos = self._anchor or _caret_pos() or _cursor_pos()
        if not pos:
            return
        x, y = pos
        w, h = self.width(), self.height()
        scr = QApplication.primaryScreen().availableGeometry()
        x = max(scr.left() + 4, min(x - 16, scr.right() - w - 4))
        y = y - h - 12                      # над кареткой/курсором
        if y < scr.top() + 4:               # не влезло сверху — показываем снизу
            y = min(y + h + 24, scr.bottom() - h - 4)
        self.move(QPoint(x, y))
        self._sync_send_button()   # кнопка «Отправить» следует за облачком
