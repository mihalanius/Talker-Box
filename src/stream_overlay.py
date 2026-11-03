# -*- coding: utf-8 -*-
"""Плавающее облачко живого текста.

Показывает распознанную речь под кареткой активного поля ввода (на 20 px ниже):
каретка берётся через UI Automation (Chrome/Edge, Telegram, VS Code, WPF), затем
через Win32 (Блокнот, WinForms), затем рамка поля с фокусом, и только в последнюю
очередь — курсор мыши. Кликам не мешает (окно прозрачно для ввода), всегда поверх.
"""
import ctypes
import math
import os
import time
from ctypes import wintypes

from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QCursor
from PyQt6.QtWidgets import (QApplication, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                             QMenu, QVBoxLayout, QWidget)

try:      # UI Automation — точная каретка там, где её рисует само приложение
    import comtypes.client
    comtypes.client.GetModule("UIAutomationCore.dll")
    import comtypes.gen.UIAutomationClient as UIA
except Exception:   # без библиотеки останутся Win32-каретка и рамка поля ввода
    UIA = None

CARET_GAP = 20      # облачко висит на столько пикселей НИЖЕ каретки


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
        self._size = 10
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
            self._size = 10
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

    def __init__(self, idle=False):
        super().__init__()
        self.setFixedSize(208, 36)   # высота — вполовину (по пикам сверху-снизу)
        self.phase = 0.0
        self._active = False          # волна живёт только пока идёт речь
        self._idle = bool(idle)       # спокойная волна «жду голос» (до речи)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(33)  # темп анимации — как в капсуле

    def set_idle(self, idle):
        """Спокойная волна (облачко ждёт речь) или обычный режим."""
        self._idle = bool(idle)
        if idle:
            self.phase = 0.0
            self._timer.start()        # спокойная волна тоже живёт — не замирает
        elif not self._active:
            self._timer.stop()
        self.update()

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
        if not self._active and not self._idle:   # тишина/отмена — волны не видно
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
            if self._active:
                v = math.sin(self.phase + i * 0.45) * 0.7
                v += math.sin(self.phase * 1.8 + i * 0.35) * 0.4
                v += math.sin(self.phase * 0.6 + i * 0.7) * 0.3
            else:                    # спокойная волна: программа слушает и ждёт голос
                v = math.sin(i * 0.9 + self.phase * 0.5) * 0.25   # плавно «дышит», но спокойно
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


_UIA_OBJ = None


def _uia():
    """Экземпляр IUIAutomation (создаётся один раз)."""
    global _UIA_OBJ
    if _UIA_OBJ is None:
        _UIA_OBJ = comtypes.client.CreateObject(
            UIA.CUIAutomation, interface=UIA.IUIAutomation)
    return _UIA_OBJ


def _dpr():
    """Масштаб экрана Qt: UIA отдаёт физические пиксели, move() ждёт логические."""
    try:
        return QApplication.primaryScreen().devicePixelRatio() or 1.0
    except Exception:
        return 1.0


def _uia_caret_pos():
    """Экранная позиция каретки через UI Automation (или None).

    Работает там, где каретку рисует само приложение: Chromium (Chrome, Edge,
    Telegram, VS Code, Electron), WPF. UI Automation отдаёт прямоугольники
    выделения; если ничего не выделено, возвращается вырожденный диапазон в
    позиции каретки — берём правый край последнего прямоугольника.
    """
    if UIA is None:
        return None
    try:
        el = _uia().GetFocusedElement()
        if not el:
            return None
        try:
            if el.CurrentProcessId == os.getpid():   # наш же интерфейс — не цель
                return None
        except Exception:
            pass
        pattern = el.GetCurrentPattern(UIA.UIA_TextPatternId)
        text = pattern.QueryInterface(UIA.IUIAutomationTextPattern)
        rects = ()
        try:
            sel = text.GetSelection()
            if sel and sel.Length:
                rects = sel.GetElement(0).GetBoundingRectangles() or ()
        except Exception:
            rects = ()
        scale = _dpr()
        for i in range(len(rects) - 4, -1, -4):
            left, top, width, height = rects[i:i + 4]
            if height < 6 or height > 260:      # не строка текста
                continue
            return (int(round((left + width) / scale)), int(round(top / scale)))
    except Exception:
        pass
    return None


def _window_pid(hwnd):
    """PID процесса, которому принадлежит окно (0 — если не удалось)."""
    try:
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value
    except Exception:
        return 0


def _focus_rect():
    """Экранный прямоугольник поля ввода с фокусом (left, top, w, h) или None.

    Без UI Automation: берём окно фокуса из GetGUIThreadInfo (тот же вызов,
    что и для каретки). Подходит только для окон, похожих на поле ввода;
    большие области (страница браузера, окно редактора, наш интерфейс)
    отбрасываются, чтобы облачко не улетало в угол экрана.
    """
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        if _window_pid(hwnd) == os.getpid():   # наш же интерфейс — не цель
            return None
        gti = GUITHREADINFO()
        gti.cbSize = ctypes.sizeof(GUITHREADINFO)
        tid = user32.GetWindowThreadProcessId(hwnd, None)
        if not user32.GetGUIThreadInfo(tid, ctypes.byref(gti)):
            return None
        target = gti.hwndFocus or gti.hwndActive
        if not target or not user32.IsWindowVisible(target):
            return None
        if _window_pid(target) == os.getpid():
            return None
        r = wintypes.RECT()
        if not user32.GetWindowRect(target, ctypes.byref(r)):
            return None
        left, top = r.left, r.top
        width, height = r.right - r.left, r.bottom - r.top
        if width < 40 or height < 14:
            return None
        if height > 260 or width > 1400:   # это окно/документ, а не поле ввода
            return None
        return (left, top, width, height)
    except Exception:
        return None


class StreamOverlay(QWidget):
    add_word_requested = pyqtSignal(str)   # выделенное слово → «Добавить в словарь»
    close_requested = pyqtSignal()         # «Закрыть» в меню = отмена сессии

    def __init__(self):
        super().__init__(None,
                         Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        # правая кнопка — меню словаря (отмена — только крестиком)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.label = QLabel("")
        self.label.setWordWrap(True)       # после предела ширины — текст идёт вниз
        self.label.setMaximumWidth(570)    # предел ширины (как у облачка сообщений)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)  # слово выделяется мышкой
        self.label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.label.customContextMenuRequested.connect(self._context_menu)
        self.label.setStyleSheet(
            "QLabel { background: transparent; color: #5c5c5c;"
            " border: none; padding: 9px 13px 2px 13px;"
            " font-size: 12px; line-height: 1.4; }")

        # нижняя строка: время диктовки и крестик сброса
        self.time_label = QLabel("")
        self.time_label.setStyleSheet(
            "QLabel { background: transparent; color: #2e8b75; border: none;"
            " padding: 0 13px 7px 13px; font-size: 9px; }")
        self.close_label = QLabel("✕")
        self.close_label.setStyleSheet(
            "QLabel { background: transparent; color: #2e8b75; border: none;"
            " font-weight: bold; padding: 0 13px 7px 13px; font-size: 13px; }")

        # место под кнопку «Отправить» — слева в нижней строке;
        # сама кнопка живёт отдельным окном поверх (ей нужны клики и курсор-рука)
        self.send_label = QLabel("[Отправить]")
        self.send_label.setStyleSheet(
            "QLabel { background: transparent; color: transparent; border: none;"
            " padding: 0 13px 7px 13px; font-size: 10px; }")
        self.send_button = SendButtonWindow()
        self.box = QWidget()
        self.box.setStyleSheet(
            "QWidget { background: #ececec; border: 1px solid #dcdcd8;"
            " border-bottom: 2px solid #d0d0cc; border-radius: 10px; }")
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
        # прозрачность текста и подписей: до речи облачко прозрачно, видна только волна
        self._fx = []
        for w_ in (self.label, self.time_label, self.close_label):
            fx = QGraphicsOpacityEffect(w_)
            fx.setOpacity(1.0)
            w_.setGraphicsEffect(fx)
            self._fx.append(fx)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.box)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._follow)
        self._timer.start(120)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        self._anchor = None        # точка привязки облачка (каретка)
        self._field_rect = None    # поле ввода с фокусом, если каретка не найдена
        self._anchor_weak = False  # позиция взята не из UI Automation — можно перепроверить
        self._anchor_deadline = 0.0
        self._anchor_tries = 0

    def show_text(self, text):
        """Показать текст: поле растёт по ширине (до предела), дальше — по высоте."""
        if not getattr(self, "_enabled", True):
            return
        if time.monotonic() < getattr(self, "_flash_until", 0.0):
            return   # после сброса держим «Сброшено» — запоздалый текст не мешает
        self._leave_idle()      # речь пошла — фон и текст проявляются
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
        # в статичном размере (минимум 380) волна уже на 50px — не наезжает на таймер;
        # когда облачко начинает расти по ширине — волна возвращается к 208px
        self._set_wave_width(158 if w <= 380 else 208)
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

    def show_idle(self):
        """Сразу после хоткея: облачко на своём месте, но фон и текст прозрачны — видна только волна."""
        if not getattr(self, "_enabled", True):
            return
        self._flash_until = 0.0
        self.label.setText("")
        self.set_time("")
        self.send_label.setVisible(False)          # кнопка «Отправить» — только когда речь
        self._set_wave_width(158)
        self.wave.set_idle(True)
        self.box.setStyleSheet(
            "QWidget { background: transparent; border: none; border-radius: 10px; }")
        for fx in self._fx:
            fx.setOpacity(0.0)
        fm = self.label.fontMetrics()
        h = self.label.heightForWidth(380) or fm.height()
        self.setFixedSize(380, h + self.wave.height() + 6)
        self.wave.show()
        self.show()
        self.raise_()
        self._follow()

    def _leave_idle(self):
        """Речь пошла: фон облачка и текст проявляются, волна переходит в обычный режим."""
        if not any(fx.opacity() < 1.0 for fx in self._fx):
            return
        for fx in self._fx:
            fx.setOpacity(1.0)
        self.wave.set_idle(False)
        self.send_label.setVisible(True)
        st = getattr(self, "_style", None)
        if st:
            self.apply_style(*st)
        else:
            self.box.setStyleSheet(
                "QWidget { background: #ececec; border: 1px solid #dcdcd8;"
                " border-bottom: 2px solid #d0d0cc; border-radius: 10px; }")

    def hide_later(self, ms=2500):
        """Скрыть через паузу (после окончания диктовки)."""
        self._hide_timer.start(ms)

    def apply_style(self, bg, fg, font_px, opacity=100, family=""):
        """Настройки облачка: фон, текст, шрифт (размер и название), прозрачность."""
        self._style = (bg, fg, font_px, opacity, family)
        # возврат к обычному виду: текст по левому краю, волна на месте
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.wave.setVisible(True)
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
            "QWidget { background: rgba(%d,%d,%d,%.2f); border: 1px solid #dcdcd8;"
            " border-bottom: 2px solid #d0d0cc; border-radius: 10px; }"
            % (r, g, b, a))
        self.label.setStyleSheet(
            "QLabel { background: transparent; color: %s; border: none; %s"
            " padding: 9px 13px 2px 13px; font-size: %dpx; line-height: 1.4; }"
            % (fg, fam, int(font_px)))
        # таймер и кнопка «Отправить» — тем же шрифтом, что и распознанный текст, но на 2px меньше
        small = max(8, int(font_px) - 2)      # «[Отправить]» — на 2px меньше текста
        timer = max(8, int(font_px) - 3)      # таймер — на 3px меньше текста
        self.time_label.setStyleSheet(
            "QLabel { background: transparent; color: #2e8b75; border: none; %s"
            " padding: 0 13px 7px 13px; font-size: %dpx; }" % (fam, timer))
        self.send_label.setStyleSheet(
            "QLabel { background: transparent; color: transparent; border: none; %s"
            " padding: 0 13px 7px 13px; font-size: %dpx; }" % (fam, small))
        self.send_button.set_font(family, small)

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

    def _set_wave_width(self, width):
        if self.wave.width() != width:
            self.wave.setFixedSize(width, self.wave.height())

    def flash_reset(self, message="Сброшено — жмите хоткей заново"):
        """Красная вспышка: диктовка отменена. Компактно и строго по центру."""
        self._flash_until = 0.0
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)   # текст по центру
        self.wave.hide()            # волны тут нет — убираем пустое место под неё
        self.show_text(message)
        self._flash_until = time.monotonic() + 2.0   # 2 секунды держим «Сброшено»
        # облако — ровно по тексту: без лишней ширины и высоты
        fm = self.label.fontMetrics()
        try:
            tw = fm.horizontalAdvance(message)
        except Exception:
            tw = fm.boundingRect(message).width()
        w = max(240, min(570, tw + 40))
        h = self.label.heightForWidth(w) or fm.height()
        self.setFixedSize(w, h + 30)   # строка текста + место под крестик
        self._follow()
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
        """Закрепить облачко у поля ввода (позиция берётся один раз, статично).

        Порядок: каретка UI Automation (браузеры, Electron, WPF) → каретка
        Win32 (Блокнот, WinForms) → поле ввода с фокусом → курсор мыши.
        """
        self._flash_until = 0.0     # новая диктовка — защита «Сброшено» снимается
        pos = _uia_caret_pos()
        if pos:
            self._anchor, self._field_rect = pos, None
            self._anchor_weak = False
            return
        self._anchor = _caret_pos()
        self._field_rect = None if self._anchor else _focus_rect()
        # первый запрос UIA к свежему окну иногда отдаёт пустой прямоугольник
        # (холодное дерево доступности) — перепроверим, пока облачко на экране
        self._anchor_weak = True
        self._anchor_tries = 0
        self._anchor_deadline = time.monotonic() + 1.5

    def clear_anchor(self):
        """Отпустить привязку (позиция будет взята заново при следующей диктовке)."""
        self._anchor = None
        self._field_rect = None
        self._anchor_weak = False

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

    def _context_menu(self, pos):
        """Правая кнопка — меню словаря (отмена диктовки — только крестиком)."""
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #ffffff; color: #222222; border: 1px solid #cccccc;"
            " padding: 4px; font-size: 12px; }"
            "QMenu::item:selected { background: #d6f5e8; }")
        selected = self.label.selectedText().strip()
        act_add = menu.addAction("Добавить в словарь…")
        act_add.setEnabled(bool(selected))   # нужно выделить слово
        act_copy = menu.addAction("Скопировать текст")
        menu.addSeparator()
        act_close = menu.addAction("Закрыть")
        action = menu.exec(QCursor.pos())
        if action is act_add:
            self.add_word_requested.emit(selected)
        elif action is act_copy:
            QApplication.clipboard().setText(self.label.text())
        elif action is act_close:
            self.close_requested.emit()   # отмена сессии — как Escape и крестик

    def replace_in_text(self, wrong, target):
        """Исправить слово в показанном тексте (после добавления в словарь)."""
        import re
        text = self.label.text()
        if not text or not wrong:
            return text
        new = re.sub(re.escape(wrong), target, text, flags=re.IGNORECASE)
        self.label.setText(new)
        return new

    def _follow(self):
        if not self.isVisible():
            return
        if (self._anchor_weak and self._anchor_tries < 6
                and time.monotonic() < self._anchor_deadline):
            self._anchor_tries += 1
            pos = _uia_caret_pos()
            if pos:
                self._anchor, self._field_rect = pos, None
                self._anchor_weak = False
        pos = self._anchor
        field = self._field_rect
        if not pos:
            field = field or _focus_rect()           # поле ввода с фокусом
            if field:
                pos = (field[0] + field[2] // 2, field[1])
            else:
                pos = _cursor_pos()
        if not pos:
            return
        x, y = pos
        w, h = self.width(), self.height()
        scr = QApplication.primaryScreen().availableGeometry()
        x = max(scr.left() + 4, min(x - 16, scr.right() - w - 4))
        # облачко висит ПОД кареткой (или под полем ввода), а не над ней
        below = (field[1] + field[3] + CARET_GAP) if field else (y + CARET_GAP)
        if below + h <= scr.bottom() - 4:
            y = below                       # влезает снизу — показываем там
        else:                               # снизу места нет — над кареткой
            y = y - h - 12
        y = max(scr.top() + 4, min(y, scr.bottom() - h - 4))
        self.move(QPoint(x, y))
        self._sync_send_button()   # кнопка «Отправить» следует за облачком
