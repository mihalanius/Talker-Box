import sys
import os
import time
import threading
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QLabel, QPushButton, QComboBox,
                              QCheckBox, QSystemTrayIcon, QMenu, QMessageBox,
                              QLineEdit, QListWidget, QFrame, QSlider, QColorDialog,
                              QScrollArea)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPointF
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QBrush, QFont, QAction, QColor, QPen, QPolygonF, QFontDatabase, QFontMetrics, QCursor, QRadialGradient
from recorder import Recorder
from transcriber import Transcriber
from stream_recognizer import PhraseStream
from stream_overlay import StreamOverlay
from settings_manager import SettingsManager
from ad_manager import AdManager
from waveform import WaveformWindow
from hotkey_hook import HotkeyListener, start_capture
from sounds import play_start_sound, play_stop_sound, play_hover_sound, play_reset_sound
from logger import log
from paths import get_base_dir, get_exe_dir


class TabButton(QPushButton):
    """Вкладка как в макете dashboard_v3: активная — светлая с тонкой рамкой и зелёной точкой."""

    def __init__(self, text):
        super().__init__(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(28)
        self.setStyleSheet("""
            QPushButton {
                background: transparent; color: #777; border: 1px solid transparent;
                border-radius: 8px; padding: 4px 12px; font-size: 11px;
            }
            QPushButton:hover { background: #dedede; color: #000; }
            QPushButton:checked {
                background: #ededea; color: #000; font-weight: bold;
                border: 1px solid #dcdcd8; padding-left: 27px;
            }
        """)
        f = QFont(self.font())
        f.setPixelSize(11)
        f.setBold(True)
        self._tw = QFontMetrics(f).horizontalAdvance(text)
        self.setFixedWidth(self._tw + 7 + 8 + 2 * 14 + 2)   # точка + отступ + текст + поля по бокам

    def _text_w(self):
        f = QFont(self.font())
        f.setPixelSize(11)
        f.setBold(True)
        return QFontMetrics(f).horizontalAdvance(self.text())

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.isChecked():
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#00c25a"))
            cx = self.width() / 2 - self._text_w() / 2 - 4   # текст сдвинут на 7.5 px вправо — точка и текст по центру кнопки
            p.drawEllipse(QPointF(cx, self.height() / 2 + 1), 3.5, 3.5)
            p.end()


class GroupTag(QLabel):
    """Бирка блока: светодиод рисуется отдельно — по центру левого отступа.

    В макете v3 точка задана как ::before у подписи. Если оставить её
    символом в тексте, она садится на базовую линию и «пляшет».
    Здесь точка рисуется по вертикальному центру бирки, а по горизонтали —
    ровно посередине между рамкой бирки и первой буквой текста.
    """

    DOT = 7          # диаметр светодиода
    PAD_LEFT = 10    # от рамки бирки до светодиода
    GAP = 6          # от светодиода до первой буквы
    PAD_RIGHT = 10
    PAD_V = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = False

    def set_tag(self, active, text):
        self._active = bool(active)
        left = self.PAD_LEFT + self.DOT + self.GAP if self._active else self.PAD_LEFT
        f = QFont(self.font())
        f.setPixelSize(11)
        f.setBold(self._active)
        self.setFont(f)
        self.setText(text)
        self.setStyleSheet(
            "QLabel { background: #e2e2df; color: #000; border: 1px solid "
            f"{'#00914a' if self._active else '#d6d6d2'}; border-radius: 4px;"
            f" padding: {self.PAD_V}px {self.PAD_RIGHT}px {self.PAD_V}px {left}px;"
            " font-size: 11px; }")
        self.adjustSize()

    def paintEvent(self, e):
        super().paintEvent(e)
        if not self._active:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#00c25a"))
        # 1 px рамки + отступ + половина диаметра = центр левого промежутка
        cx = 1 + self.PAD_LEFT + self.DOT / 2.0
        cy = self.height() / 2.0
        p.drawEllipse(QPointF(cx, cy), self.DOT / 2.0, self.DOT / 2.0)
        p.end()


class GroupBox(QWidget):
    """Блок с биркой на верхней границе — как .group-box в dashboard_v3."""

    def __init__(self, title, content=None, active=False, inner=True):
        super().__init__()
        self._title = title
        self.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 9, 0, 0)
        outer.setSpacing(0)
        self._frame = QWidget()
        self._frame.setObjectName("gbframe")
        self._frame_lay = QVBoxLayout(self._frame)
        self._frame_lay.setContentsMargins(14, 14, 14, 14)
        self._frame_lay.setSpacing(0)
        # inner=False — содержимое кладётся прямо в блок (как «Настройки» в макете)
        self._inner = None
        self._inner_lay = None
        if inner:
            self._inner = QWidget()
            self._inner.setObjectName("gbinner")
            self._inner.setStyleSheet("#gbinner { background: #f7f7f5; border: 1px solid #e2e2df; border-radius: 8px; }")
            self._inner_lay = QVBoxLayout(self._inner)
            self._inner_lay.setContentsMargins(12, 14, 12, 14)
            self._inner_lay.setSpacing(0)
            self._frame_lay.addWidget(self._inner)
        else:
            self._frame_lay.setContentsMargins(16, 22, 16, 10)
        outer.addWidget(self._frame)
        self._tag = GroupTag(self)
        self._tag.move(12, 0)
        self.set_active(active)
        if content is not None:
            self.set_content(content)

    def set_content(self, content):
        (self._inner_lay if self._inner is not None else self._frame_lay).addWidget(content)

    def set_active(self, active):
        self._active = bool(active)
        border = "#00914a" if active else "#dcdcd8"
        self._frame.setStyleSheet(
            f"#gbframe {{ background: #ebebe8; border: 1px solid {border}; border-radius: 10px; }}")
        self._tag.set_tag(self._active, self._title)
        self._tag.raise_()


class NeonFrame(QFrame):
    def __init__(self, parent=None, color="#00ff88", corner_size=12, thickness=2):
        super().__init__(parent)
        self._color = QColor(color)
        self._corner_size = corner_size
        self._thickness = thickness
        self.setStyleSheet("background: transparent; border: none;")

    def _draw_tapered_line(self, painter, x1, y1, x2, y2):
        r, g, b = self._color.red(), self._color.green(), self._color.blue()
        steps = 12
        dx = (x2 - x1) / steps
        dy = (y2 - y1) / steps
        for i in range(steps):
            t = i / steps
            thick = max(1, int(self._thickness * (1 - t)))
            alpha = int(255 * (1 - t * 0.7))
            pen = QPen(QColor(r, g, b, alpha), thick)
            painter.setPen(pen)
            sx = x1 + dx * i
            sy = y1 + dy * i
            ex = x1 + dx * (i + 1)
            ey = y1 + dy * (i + 1)
            painter.drawLine(int(sx), int(sy), int(ex), int(ey))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h, s = self.width(), self.height(), self._corner_size
        self._draw_tapered_line(painter, 0, s, 0, 0)
        self._draw_tapered_line(painter, 0, 0, s, 0)
        self._draw_tapered_line(painter, w - s, 0, w, 0)
        self._draw_tapered_line(painter, w, 0, w, s)
        self._draw_tapered_line(painter, 0, h - s, 0, h)
        self._draw_tapered_line(painter, 0, h, s, h)
        self._draw_tapered_line(painter, w - s, h, w, h)
        self._draw_tapered_line(painter, w, h - s, w, h)
        painter.end()


class NeonGroupBox(QWidget):
    def __init__(self, title="", parent=None, color="#00ff88", corner_size=14, thickness=3, show_corners=True):
        super().__init__(parent)
        self._title = title
        self._color = QColor(color)
        self._corner_size = corner_size
        self._thickness = thickness
        self._show_corners = show_corners
        self.setStyleSheet("background: transparent;")

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        if title:
            self._title_label = QLabel(title)
            self._title_label.setStyleSheet(f"color: {color}; background: transparent; font: bold 11px 'Segoe UI';")
            self._title_label.setContentsMargins(15, 0, 0, 0)
            self._title_label.setFixedHeight(16)
            self._outer.addWidget(self._title_label)

        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(15, 0, 10, 0)
        self._outer.addWidget(self._inner)

    def layout(self):
        return self._layout

    def _draw_tapered_line(self, painter, x1, y1, x2, y2):
        r, g, b = self._color.red(), self._color.green(), self._color.blue()
        steps = 12
        dx = (x2 - x1) / steps
        dy = (y2 - y1) / steps
        for i in range(steps):
            t = i / steps
            thick = max(1, int(self._thickness * (1 - t)))
            alpha = int(255 * (1 - t * 0.7))
            pen = QPen(QColor(r, g, b, alpha), thick)
            painter.setPen(pen)
            sx = x1 + dx * i
            sy = y1 + dy * i
            ex = x1 + dx * (i + 1)
            ey = y1 + dy * (i + 1)
            painter.drawLine(int(sx), int(sy), int(ex), int(ey))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h, s = self.width(), self.height(), self._corner_size
        if self._show_corners:
            self._draw_tapered_line(painter, 0, s, 0, 0)
            self._draw_tapered_line(painter, 0, 0, s, 0)
            self._draw_tapered_line(painter, w - s, 0, w, 0)
            self._draw_tapered_line(painter, w, 0, w, s)
            self._draw_tapered_line(painter, 0, h - s, 0, h)
            self._draw_tapered_line(painter, 0, h, s, h)
            self._draw_tapered_line(painter, w - s, h, w, h)
            self._draw_tapered_line(painter, w, h - s, w, h)
        if self._title:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            dash_pen = QPen(self._color, 1, Qt.PenStyle.DashLine)
            painter.setPen(dash_pen)
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(self._title) + 20
            painter.drawLine(text_w, 8, w - s - 4, 8)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.end()


class NeonLabel(QWidget):
    def __init__(self, text="", font_size=16, color="#00ff88", parent=None):
        super().__init__(parent)
        self._text = text
        self._font_size = font_size
        self._color = QColor(color)
        self._font_family = "Segoe UI"
        self.setStyleSheet("background: transparent;")
        font = QFont(self._font_family, self._font_size)
        font.setBold(True)
        fm = QFontMetrics(font)
        self.setFixedSize(fm.horizontalAdvance(text) + 40, fm.height() + 20)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(self._font_family, self._font_size)
        font.setBold(True)
        p.setFont(font)
        r, g, b = self._color.red(), self._color.green(), self._color.blue()
        fm = p.fontMetrics()
        x = (self.width() - fm.horizontalAdvance(self._text)) // 2
        y = self.height() // 2 + fm.ascent() // 2
        for blur_r in [10, 6, 3]:
            alpha = max(5, int(40 * (1 - blur_r / 10)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(r, g, b, alpha)))
            for dx in range(-blur_r, blur_r + 1, 2):
                for dy in range(-blur_r, blur_r + 1, 2):
                    if dx * dx + dy * dy <= blur_r * blur_r:
                        p.drawText(x + dx, y + dy, self._text)
        p.setPen(QPen(self._color, 1))
        p.drawText(x, y, self._text)
        p.end()


class NeonCheckBox(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, checked=True, parent=None):
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(14, 14)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        self._checked = checked
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._checked:
            p.setPen(QPen(QColor("#00ff88"), 1.5))
            p.setBrush(QBrush(QColor("#00ff88")))
        else:
            p.setPen(QPen(QColor("#00ff88"), 1.5))
            p.setBrush(QBrush(QColor("#16213e")))

        p.drawRect(1, 1, 12, 12)

        if self._checked:
            p.setPen(QPen(QColor("#0a0a2e"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawLine(4, 7, 6, 10)
            p.drawLine(6, 10, 10, 4)

        p.end()

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self.update()
        self.toggled.emit(self._checked)


class ToggleSwitch(QWidget):
    """Тумблер как в макете dashboard_v3: 36×20, светлый, без свечения."""

    toggled = pyqtSignal(bool)

    W, H = 36, 20

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self._checked = bool(checked)
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        checked = bool(checked)
        if checked != self._checked:
            self._checked = checked
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#c6c6c2" if self._checked else "#cccccc"))
        p.drawRoundedRect(0, 0, self.W, self.H, self.H / 2, self.H / 2)
        p.setBrush(QColor("#ffffff"))
        p.setPen(QPen(QColor(0, 0, 0, 45), 1))
        x = self.W - 2 - 16 if self._checked else 2
        p.drawEllipse(x, 2, 16, 16)
        p.end()

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self.update()
        self.toggled.emit(self._checked)


class TaperedBar(QLabel):
    def __init__(self, parent=None, color="#333", height=5):
        super().__init__(parent)
        self._color = color
        self.setFixedHeight(height)
        self._update_style()

    def set_color(self, color):
        self._color = color
        self._update_style()

    def _update_style(self):
        c = self._color
        self.setStyleSheet(f"""
            QLabel {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba({self._hex_to_rgb(c)}, 0),
                    stop:0.15 rgba({self._hex_to_rgb(c)}, 255),
                    stop:0.85 rgba({self._hex_to_rgb(c)}, 255),
                    stop:1.0 rgba({self._hex_to_rgb(c)}, 0));
                border-radius: 2px;
            }}
        """)

    def _hex_to_rgb(self, hex_color):
        h = hex_color.lstrip('#')
        if len(h) == 3:
            h = h[0]*2 + h[1]*2 + h[2]*2
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r},{g},{b}"


class Signals(QObject):
    text_ready = pyqtSignal(str)
    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()
    transcribing_started = pyqtSignal()
    transcribing_finished = pyqtSignal()
    hotkey_captured = pyqtSignal(str)
    stream_phrase = pyqtSignal(str, bool)   # живой текст: (текст, это черновик)
    session_text = pyqtSignal(str)          # точный текст диктовки (как уйдёт в поле)


def _paste_via_sendinput(text, auto_send=False, is_terminal=False):
    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    class INPUT(ctypes.Structure):
        pass

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.wintypes.WORD),
            ("wScan", ctypes.wintypes.WORD),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("time", ctypes.wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.wintypes.LONG),
            ("dy", ctypes.wintypes.LONG),
            ("mouseData", ctypes.wintypes.DWORD),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("time", ctypes.wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", ctypes.wintypes.DWORD),
            ("wParamL", ctypes.wintypes.WORD),
            ("wParamH", ctypes.wintypes.WORD),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("ki", KEYBDINPUT),
            ("mi", MOUSEINPUT),
            ("hi", HARDWAREINPUT),
        ]

    INPUT._fields_ = [
        ("type", ctypes.wintypes.DWORD),
        ("union", _INPUT_UNION),
    ]

    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004

    def send_key(vk, flags=0):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = vk
        inp.union.ki.dwFlags = flags
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def send_unicode(ch):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = 0
        inp.union.ki.wScan = ord(ch)
        inp.union.ki.dwFlags = KEYEVENTF_UNICODE
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    VK_RETURN = 0x0D
    VK_TAB = 0x09

    # печатаем текст СИМВОЛАМИ через SendInput — буфер обмена не трогаем ВООБЩЕ,
    # чтобы скопированные картинки и текст оставались на месте
    units = []
    for ch in text:
        cp = ord(ch)
        if cp > 0xFFFF:                      # символы вне BMP — суррогатной парой
            cp -= 0x10000
            units.append(0xD800 + (cp >> 10))
            units.append(0xDC00 + (cp & 0x3FF))
        else:
            units.append(cp)

    inputs = []

    def push(vk, scan, flags):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = vk
        inp.union.ki.wScan = scan
        inp.union.ki.dwFlags = flags
        inputs.append(inp)

    for u in units:
        if u in (0x0D, 0x0A):                # перевод строки — как клавиша Enter
            push(VK_RETURN, 0, 0)
            push(VK_RETURN, 0, KEYEVENTF_KEYUP)
        elif u == 0x09:                      # табуляция
            push(VK_TAB, 0, 0)
            push(VK_TAB, 0, KEYEVENTF_KEYUP)
        else:
            push(0, u, KEYEVENTF_UNICODE)
            push(0, u, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)

    # шлём пачками — быстро и без «заеданий»
    batch = 64
    for i in range(0, len(inputs), batch):
        chunk = inputs[i:i + batch]
        arr = (INPUT * len(chunk))(*chunk)
        sent = user32.SendInput(len(chunk), arr, ctypes.sizeof(INPUT))
        if sent != len(chunk):
            # очередь ввода переполнилась — добиваем остаток по одному,
            # иначе длинный текст вставляется частично
            for one in chunk[sent or 0:]:
                user32.SendInput(1, ctypes.byref(one), ctypes.sizeof(INPUT))
                time.sleep(0.003)
        time.sleep(0.01)

    if auto_send:
        time.sleep(0.15)
        send_key(VK_RETURN)
        time.sleep(0.03)
        send_key(VK_RETURN, KEYEVENTF_KEYUP)


TERMINAL_CLASSES = {
    "ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS",
    "mintty", "VirtualConsoleClass", "Alacritty",
    "org.wezfurlong.wezterm",
}
TERMINAL_EXES = {
    "tabby.exe", "wave.exe", "rio.exe", "termius.exe",
}


def _is_terminal():
    import ctypes
    import ctypes.wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False

    try:
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        cls = buf.value

        if cls in TERMINAL_CLASSES:
            return True

        exe_buf = ctypes.create_unicode_buffer(260)
        handle = kernel32.OpenProcess(0x0400, False, pid.value)
        if handle:
            kernel32.GetModuleFileNameW(handle, exe_buf, 260)
            kernel32.CloseHandle(handle)
            exe = os.path.basename(exe_buf.value).lower()
            if exe in TERMINAL_EXES:
                return True
    except Exception:
        pass
    return False


class MainWindow(QMainWindow):
    _hotkey_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._hotkey_signal.connect(self._on_hotkey_event, Qt.ConnectionType.QueuedConnection)
        self.settings = SettingsManager()
        self.recorder = Recorder()
        # живое распознавание (GigaAM) + облачко над полем ввода
        self.phrase_stream = PhraseStream(None, lambda t, p=False: self.signals.stream_phrase.emit(t, p))
        self.stream_overlay = StreamOverlay()
        self.stream_overlay.send_button.clicked.connect(self._on_send_click)   # «Отправить» = второй жм хоткея
        self.stream_overlay.add_word_requested.connect(self._on_add_word_request)   # ПКМ → словарь
        self.stream_overlay.close_requested.connect(self.cancel_session)            # «Закрыть» = отмена
        # стиль облачка из настроек — сразу при старте (таймер и «Отправить» считаются от шрифта текста)
        self.stream_overlay.apply_style(
            self.settings.get("cloud_bg", "#ececec"),
            self.settings.get("cloud_fg", "#5c5c5c"),
            self.settings.get("cloud_font", 16),
            self.settings.get("cloud_opacity", 100),
            self.settings.get("cloud_font_name", ""))
        self._stream_committed = ""
        self._session_busy = False
        self._rmb_was_down = False
        # правая кнопка мыши во время диктовки — сброс и чтение заново
        self._rmb_timer = QTimer(self)
        self._rmb_timer.timeout.connect(self._check_rmb_reset)
        self._rmb_timer.start(30)   # часто — чтобы короткий клик по крестику не проскакивал
        self.transcriber = None
        self.ad_manager = AdManager()
        self.signals = Signals()
        self.signals.session_text.connect(self._on_session_text)
        self.is_recording = False
        self.is_transcribing = False
        self.hold_mode = False
        self._suppress_hotkey = False
        self._stream_epoch = 0      # поколение сессии: гасит запоздалый текст после сброса
        self._pending_send = False  # облачко держит готовый текст: следующий хоткей его ОТПРАВИТ
        self._cloud_edited = False  # текст в облачке правили руками — финальный ASR его не затирает
        # облачко трогали мышкой (выделяли слово/правили словарь) — тогда текст ждёт,
        # иначе остановка отправляет его сразу, как раньше
        self._cloud_touched = False
        self._keep_for_edit = False
        self._last_foreign = 0      # последнее активное ЧУЖОЕ окно (куда печатать)
        self._hotkey_listener = None

        self.signals.text_ready.connect(self.on_text_ready)
        self.signals.recording_started.connect(self.on_recording_started)
        self.signals.recording_stopped.connect(self.on_recording_stopped)
        self.signals.transcribing_started.connect(self.on_transcribing_started)
        self.signals.transcribing_finished.connect(self.on_transcribing_finished)
        self.signals.hotkey_captured.connect(self._on_hotkey_captured)

        self.init_ui()
        self.init_tray()
        self.init_hotkey()
        self.load_active_model()
        self.init_ad_timer()
        self.init_waveform()
        self.show()

        if self.settings.get("minimize_to_tray") and "--minimized" in sys.argv:
            QTimer.singleShot(100, self.hide_to_tray)

    def init_ui(self):
        self.setWindowTitle("Talker Box")
        icon_path = os.path.join(get_base_dir(), "talker_box.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setFixedSize(730, 404)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)   # без рамки Windows: внешний размер 730×404
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)  # окно всегда поверх остальных
        self.setStyleSheet("""
            QMainWindow { background: #d9d9d6; }
            QLabel { color: #000; background: transparent; }
            QMessageBox { background-color: #f7f7f5; }
            QMessageBox QLabel { color: #000; }
            QPushButton {
                background-color: #ffffff;
                color: #444;
                border: 1px solid #dcdcd8;
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover { background: #f2f2f0; color: #1c1c1c; }
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
            QScrollBar::handle:vertical { background: #c6c6c2; border-radius: 4px; min-height: 24px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        central = QWidget()
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(0)

        header = QHBoxLayout()
        header.setSpacing(6)
        # блок «логотип + название + слоган»: каждый элемент — отдельный слой
        # со своей координатой, чтобы можно было двигать в любую сторону
        brand = QWidget()
        brand.setFixedSize(150, 42)
        brand.setStyleSheet("background: transparent;")
        logo_label = QLabel(brand)
        logo_label.setFixedSize(32, 32)
        logo_label.move(0, 9)         # слой логотипа: вниз/вверх и влево/вправо — менять здесь
        logo_label.setStyleSheet("background: transparent;")
        logo_label.paintEvent = lambda e: self._paint_cube_logo(logo_label, e)
        title = QLabel("Talker Box", brand)
        title.setStyleSheet("color: #000; font: bold 19px 'Segoe UI'; background: transparent;")
        font_path = os.path.join(get_base_dir(), "fonts", "Orbitron.ttf")
        if os.path.exists(font_path):
            QFontDatabase.addApplicationFont(font_path)
            title._font_family = "Orbitron"
        title.move(40, 0)             # слой названия
        slogan = QLabel("Пишите голосом", brand)
        slogan.setStyleSheet("color: #6b6b6b; font: 11px 'Segoe UI'; background: transparent;"
                             " margin: 0; padding: 0 0 0 1px;")   # шрифт 11 px, сдвиг на 1 px вправо
        slogan.move(40, 22)           # слой слогана: поднят на 2 px ближе к названию (было 24)
        header.addWidget(brand)
        root.addLayout(header)

        # живой текст показывается в плавающем облачке над полем ввода
        self.signals.stream_phrase.connect(self._on_stream_phrase)

        main_row = QHBoxLayout()
        main_row.setSpacing(12)

        # какой режим сохранён — такая и подсветка при запуске (по умолчанию «нажал-нажал»)
        saved_mode = self.settings.get("mode", "toggle")
        self.hold_panel = self._create_mode_panel("Режим Hold", "Удерживать",
            "Нажмите и удерживайте горячую клавишу пока диктуете текст и микрофон активен.",
            saved_mode == "hold")
        center_widget = self._create_center_widget()
        main_row.addWidget(center_widget, 1)
        main_row.addWidget(self.hold_panel)

        self.toggle_panel = self._create_mode_panel("Режим Toggle", "Нажал \u2014 нажал",
            "Нажмите Хоткей, чтобы начать запись и снова нажмите чтобы остановить запись.",
            saved_mode != "hold")
        main_row.addWidget(self.toggle_panel)
        root.addLayout(main_row)

        # нижние карточки «Авто-отправка» и «Горячая клавиша» из макета v3 живут
        # на вкладке «Настройки» — здесь их больше нет

        # ===== Вкладки: Главная / Настройки / Словарь / История / О программе =====
        tabs = QHBoxLayout()
        tabs.setSpacing(6)
        self.btn_tab_main = TabButton("Главная")
        self.btn_tab_set = TabButton("Настройки")
        self.btn_tab_dict = TabButton("Словарь")
        self.btn_tab_hist = TabButton("История")
        self.btn_tab_help = TabButton("Инфо")
        self.btn_tab_main.clicked.connect(lambda: self._show_tab("main"))
        self.btn_tab_set.clicked.connect(lambda: self._show_tab("settings"))
        self.btn_tab_dict.clicked.connect(lambda: self._show_tab("dict"))
        self.btn_tab_hist.clicked.connect(lambda: self._show_tab("hist"))
        self.btn_tab_help.clicked.connect(lambda: self._show_tab("help"))
        for b in (self.btn_tab_main, self.btn_tab_set, self.btn_tab_dict,
                  self.btn_tab_hist, self.btn_tab_help):
            tabs.addWidget(b)
        tabs.addStretch()
        tabs.setContentsMargins(18, 0, 0, 0)
        header.addLayout(tabs)   # вкладки в одной строке с названием, сразу за ним
        win_btns = QHBoxLayout()
        win_btns.setSpacing(4)
        btn_min = QPushButton("\u2014")
        btn_min.setFixedSize(26, 26)
        btn_min.setStyleSheet("QPushButton { background: transparent; color: #555; border: none;"
                              " border-radius: 6px; font-size: 13px; }"
                              "QPushButton:hover { background: #dedede; color: #000; }")
        btn_min.clicked.connect(self.showMinimized)
        btn_close = QPushButton("\u2715")
        btn_close.setFixedSize(26, 26)
        btn_close.setStyleSheet("QPushButton { background: transparent; color: #555; border: none;"
                                " border-radius: 6px; font-size: 12px; }"
                                "QPushButton:hover { background: #dedede; color: #000; }")
        btn_close.clicked.connect(self.close)   # закрытие = сворачивание в трей, как раньше
        win_btns.addWidget(btn_min)
        win_btns.addWidget(btn_close)
        header.addLayout(win_btns)
        header.addStretch()   # вкладки прижаты к названию, кнопки окна — к правому краю
        logo_label.mousePressEvent = self._start_drag
        title.mousePressEvent = self._start_drag
        slogan.mousePressEvent = self._start_drag
        brand.mousePressEvent = self._start_drag

        # содержимое окна становится страницей «Главная» (окно не растёт)
        self.main_page = QWidget()
        main_layout = QVBoxLayout(self.main_page)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        while root.count() > 1:
            item = root.takeAt(1)
            if item.widget():
                main_layout.addWidget(item.widget())
            elif item.layout():
                main_layout.addLayout(item.layout())
            elif item.spacerItem():
                main_layout.addSpacerItem(item.spacerItem())
        # светлый контейнер содержимого, как .content в макете
        self.content = QWidget()
        self.content.setObjectName("content")
        self.content.setStyleSheet("#content { background: #cfcfcc; border-radius: 12px; }")
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(16, 20, 16, 16)
        self.content_lay.setSpacing(0)
        root.addSpacing(15)   # отступ от названия и вкладок до светлого контейнера
        root.addWidget(self.content)
        self.content.mousePressEvent = self._start_drag   # за светлый фон страниц окно тоже тянется
        self.mousePressEvent = self._start_drag            # за пустой фон окна и шапки

        self.main_scroll = self._scroll(self.main_page)
        self.content_lay.addWidget(self.main_scroll)

        # страницы в прокрутке: окно фиксированного размера, длинное содержимое скроллится
        self.settings_page = QWidget()
        self._build_settings_page()
        self.settings_scroll = self._scroll(self.settings_page)
        self.content_lay.addWidget(self.settings_scroll)
        self.settings_scroll.hide()

        self.dict_page = QWidget()
        self._build_dict_page()
        self.dict_scroll = self._scroll(self.dict_page)
        self.content_lay.addWidget(self.dict_scroll)
        self.dict_scroll.hide()

        self.hist_page = QWidget()
        self._build_hist_page()
        self.hist_scroll = self._scroll(self.hist_page)
        self.content_lay.addWidget(self.hist_scroll)
        self.hist_scroll.hide()

        self.help_page = QWidget()
        self._build_help_page()
        self.help_scroll = self._scroll(self.help_page)
        self.content_lay.addWidget(self.help_scroll)
        self.help_scroll.hide()
        self._show_tab("main")

    def _scroll(self, page):
        sc = QScrollArea()
        sc.setWidget(page)
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.Shape.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page.setStyleSheet("background: transparent;")
        return sc

    def _build_dict_page(self):
        lay = QVBoxLayout(self.dict_page)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        title = QLabel("Словарь")
        title.setStyleSheet("color: #000; font: bold 13px 'Segoe UI'; background: transparent; border: none;")
        lay.addWidget(title)
        text = QLabel(
            "Слова, которые модель распознаёт неправильно, задаются текстовыми файлами в папке словарей.\n"
            "Формат строки: Правильное слово - неправильный1, неправильный2.\n"
            "Строки с # — комментарии. Слова из облачка (ПКМ → «Добавить в словарь») дописываются сюда же.")
        text.setStyleSheet("color: #222; font: 11px 'Segoe UI'; background: transparent; border: none;")
        text.setWordWrap(True)
        lay.addWidget(text)
        btn = QPushButton("Открыть папку словаря")
        btn.setFixedHeight(27)
        btn.clicked.connect(self._open_vocabulary_folder)
        lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addStretch()

    def _build_hist_page(self):
        lay = QVBoxLayout(self.hist_page)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        title = QLabel("История")
        title.setStyleSheet("color: #000; font: bold 13px 'Segoe UI'; background: transparent; border: none;")
        lay.addWidget(title)
        text = QLabel("История распознавания появится в следующей версии.")
        text.setStyleSheet("color: #222; font: 11px 'Segoe UI'; background: transparent; border: none;")
        text.setWordWrap(True)
        lay.addWidget(text)
        lay.addStretch()

    def _build_help_page(self):
        lay = QVBoxLayout(self.help_page)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        title = QLabel("Справка")
        title.setStyleSheet("color: #00ff88; font: bold 13px 'Segoe UI'; background: transparent; border: none;")
        lay.addWidget(title)
        text = QLabel(
            "1. Откройте программу, где будете писать текст голосом, и нажмите в поле ввода.\n"
            "2. Нажмите горячую клавишу и начинайте диктовать текст.\n"
            "3. Над полем ввода появится облачко — в нём видно, как модель слышит вашу речь.\n"
            "4. Пауза в речи — фраза выравнивается в точный текст (тот, что уйдёт в поле).\n"
            "5. Увидели ошибку? Правая кнопка мыши или крестик в облачке — сброс\n"
            "    (со звуком и красной подсветкой). Диктовку продолжаете по новой клавише.\n"
            "6. Текст отправляется в поле ввода автоматически — облачко исчезает.\n\n"
            "Настройки облачка (цвет, шрифт, прозрачность, микрофон) — на вкладке «Настройки».\n"
            "Если текст распознаётся хуже — поднесите микрофон ближе или выберите\n"
            "внешний микрофон в настройках программы.")
        text.setStyleSheet("color: #9a9a9a; font: 12px 'Segoe UI'; background: transparent; border: none;")
        text.setWordWrap(True)
        lay.addWidget(text)
        lay.addStretch()

    def _tab_style(self, active):
        return ("QPushButton { color: %s; background: %s; border: 1px solid rgba(0,255,136,%s);"
                " border-radius: 4px; font: bold 11px 'Segoe UI'; padding: 0 12px; }"
                "QPushButton:hover { border-color: #00ff88; }") % (
            "#00ff88" if active else "#7fa",
            "rgba(0,255,136,0.12)" if active else "transparent",
            "0.6" if active else "0.25")

    def _show_tab(self, which):
        pages = {"main": self.main_scroll, "settings": self.settings_scroll, "dict": self.dict_scroll,
                 "hist": self.hist_scroll, "help": self.help_scroll}
        buttons = {"main": self.btn_tab_main, "settings": self.btn_tab_set, "dict": self.btn_tab_dict,
                   "hist": self.btn_tab_hist, "help": self.btn_tab_help}
        for key, sc in pages.items():
            sc.setVisible(key == which)
        for key, b in buttons.items():
            b.setChecked(key == which)

    # ---------- вкладка «Настройки» — макет dashboard_v3 ----------

    def _set_label(self, text):
        lab = QLabel(text)
        lab.setStyleSheet("color: #000; font: 600 11px 'Segoe UI'; background: transparent; border: none;")
        return lab

    def _set_desc(self, text):
        lab = QLabel(text)
        lab.setStyleSheet("color: #222; font: 10px 'Segoe UI'; background: transparent; border: none;")
        lab.setWordWrap(True)
        return lab

    def _set_text_block(self, title, desc=None):
        """Подпись + описание — левая часть строки настроек."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(self._set_label(title))
        if desc:
            lay.addWidget(self._set_desc(desc))
        return w

    def _settings_row(self, first=False):
        """Строка на всю ширину; разделитель #5c5c5c через обе колонки, как в макете."""
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        box = QVBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        if not first:
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet("background: #5c5c5c; border: none;")
            box.addWidget(line)
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(body)
        lay.setContentsMargins(2, 8, 2, 8)
        lay.setSpacing(16)
        box.addWidget(body)
        return row, lay

    def _settings_cell(self):
        cell = QWidget()
        cell.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(cell)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        return cell, lay

    def _combo_style(self):
        return ("QComboBox { background: #fafafa; color: #1c1c1c; border: 1px solid #dcdcd8;"
                " border-radius: 8px; padding: 0 9px; font: 11px 'Segoe UI'; }"
                "QComboBox:hover { background: #ffffff; border-color: #b8b8b4; }"
                "QComboBox::drop-down { border: none; width: 18px; }"
                "QComboBox QAbstractItemView { background: #ffffff; color: #1c1c1c;"
                " border: 1px solid #dcdcd8; outline: none;"
                " selection-background-color: #e8e8e4; selection-color: #000000; }")

    def _hotkey_btn_style(self, capturing=False):
        if capturing:
            return ("QPushButton { background: #00c25a; color: #ffffff; border: 1px solid #00c25a;"
                    " border-radius: 8px; padding: 0 14px; font: 600 11px 'Segoe UI'; }")
        return ("QPushButton { background: #ffffff; color: #444; border: 1px solid #dcdcd8;"
                " border-radius: 8px; padding: 0 14px; font: 11px 'Segoe UI'; }"
                "QPushButton:hover { background: #f2f2f0; color: #1c1c1c; }")

    def _cloud_color_btn(self, key, default):
        b = QPushButton("Цвет")
        b.setFixedSize(56, 27)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            "QPushButton { background: #ffffff; color: #444; border: 1px solid #dcdcd8;"
            " border-radius: 8px; padding: 0; font: 11px 'Segoe UI'; }"
            "QPushButton:hover { background: #f2f2f0; color: #1c1c1c; }")
        b.setToolTip("Цвет фона облачка" if key == "cloud_bg" else "Цвет текста в облачке")
        b.clicked.connect(lambda: self._pick_cloud_color(key, default))
        return b

    def _build_settings_page(self):
        lay = QVBoxLayout(self.settings_page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        group = GroupBox("Настройки программы", inner=False)
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        grid = QVBoxLayout(content)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        # --- строка 1: горячая клавиша ---
        row, body = self._settings_row(first=True)
        left, ll = self._settings_cell()
        ll.addWidget(self._set_text_block("Горячая клавиша",
                                          "Нажмите любую клавишу или комбинацию"))
        ll.addStretch()
        body.addWidget(left, 1)

        right, rl = self._settings_cell()
        rl.addStretch()
        self.hotkey_btn = QPushButton(self._format_hotkey(self.settings.get("hotkey", "ctrl+win")))
        self.hotkey_btn.setFixedHeight(27)
        self.hotkey_btn.setMinimumWidth(120)
        self.hotkey_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hotkey_btn.setStyleSheet(self._hotkey_btn_style())
        self.hotkey_btn.clicked.connect(self.start_hotkey_capture)
        self._capturing_hotkey = False
        rl.addWidget(self.hotkey_btn)
        body.addWidget(right, 1)
        grid.addWidget(row)

        # --- строка 2: облако текста, цвет фона, прозрачность, вкл/выкл ---
        row, body = self._settings_row()
        left, ll = self._settings_cell()
        ll.addWidget(self._set_text_block("Облако распознаваемого текста",
                                          "Отображает текст на экране в облачке"))
        ll.addStretch()
        ll.addWidget(self._cloud_color_btn("cloud_bg", "#ececec"))
        body.addWidget(left, 1)

        right, rl = self._settings_cell()
        rl.addWidget(self._set_label("Прозрачность:"))
        self.cloud_opacity = QSlider(Qt.Orientation.Horizontal)
        self.cloud_opacity.setRange(20, 100)
        self.cloud_opacity.setValue(int(self.settings.get("cloud_opacity", 100)))
        self.cloud_opacity.setFixedWidth(80)
        self.cloud_opacity.setStyleSheet(
            "QSlider::groove:horizontal { height: 3px; background: #c6c6c2; border-radius: 2px; }"
            "QSlider::sub-page:horizontal { background: #c6c6c2; border-radius: 2px; }"
            "QSlider::handle:horizontal { width: 13px; height: 13px; margin: -5px 0;"
            " border-radius: 6px; background: #f2f2f0; border: 1px solid #b8b8b4; }")
        self.cloud_opacity.valueChanged.connect(self._apply_cloud_settings)
        rl.addWidget(self.cloud_opacity)
        rl.addStretch()
        self.cloud_toggle = ToggleSwitch(checked=self.settings.get("cloud_enabled", True))
        self.cloud_toggle.toggled.connect(self._toggle_cloud)
        rl.addWidget(self.cloud_toggle)
        body.addWidget(right, 1)
        grid.addWidget(row)

        # --- строка 3: шрифт и размер, цвет текста ---
        row, body = self._settings_row()
        left, ll = self._settings_cell()
        ll.addWidget(self._set_label("Шрифт"))

        self.cloud_font_name = QComboBox()
        self.cloud_font_name.setFixedHeight(27)
        self.cloud_font_name.setMinimumWidth(150)
        self.cloud_font_name.setStyleSheet(self._combo_style())
        view = self.cloud_font_name.view()
        view.setStyleSheet("QListView { background: #ffffff; color: #1c1c1c;"
                           " border: 1px solid #dcdcd8; outline: none; }")
        families = QFontDatabase.families()
        self.cloud_font_name.addItem("(по умолчанию)")
        for fam in families:
            self.cloud_font_name.addItem(fam)
            idx = self.cloud_font_name.count() - 1
            # белый фон, чёрный текст, своё начертание — всё видно сразу
            self.cloud_font_name.setItemData(idx, QColor("#1c1c1c"), Qt.ItemDataRole.ForegroundRole)
            self.cloud_font_name.setItemData(idx, QColor("#ffffff"), Qt.ItemDataRole.BackgroundRole)
            self.cloud_font_name.setItemData(idx, QFont(fam), Qt.ItemDataRole.FontRole)
        saved = self.settings.get("cloud_font_name", "")
        if saved and saved in families:
            self.cloud_font_name.setCurrentText(saved)
        self.cloud_font_name.currentTextChanged.connect(self._apply_cloud_settings)
        ll.addWidget(self.cloud_font_name, 1)

        self.cloud_font_size = QComboBox()
        self.cloud_font_size.setFixedSize(56, 27)
        self.cloud_font_size.setEditable(False)   # только выбор из списка, текст ввести нельзя
        self.cloud_font_size.setStyleSheet(self._combo_style())
        sizes = ["14", "16", "18"]
        self.cloud_font_size.addItems(sizes)
        saved_size = str(self.settings.get("cloud_font", 16))
        if saved_size not in sizes:   # старое значение вне списка — берём ближайшее
            try:
                saved_size = min(sizes, key=lambda s: abs(int(s) - int(saved_size)))
            except Exception:
                saved_size = "16"
        self.cloud_font_size.setCurrentText(saved_size)
        self.cloud_font_size.currentTextChanged.connect(self._apply_cloud_settings)
        ll.addWidget(self.cloud_font_size)
        body.addWidget(left, 1)

        right, rl = self._settings_cell()
        rl.addStretch()
        rl.addWidget(self._cloud_color_btn("cloud_fg", "#5c5c5c"))
        body.addWidget(right, 1)
        grid.addWidget(row)

        # --- строка 4: микрофон и авто-отправка ---
        row, body = self._settings_row()
        left, ll = self._settings_cell()
        ll.addWidget(self._set_label("Микрофон:"))
        self.mic_combo = QComboBox()
        self.mic_combo.setFixedHeight(27)
        self.mic_combo.setMinimumWidth(150)
        self.mic_combo.setStyleSheet(self._combo_style())
        self.mic_combo.addItem("(системный по умолчанию)")
        try:
            import sounddevice as _sd
            for d in _sd.query_devices():
                if d.get("max_input_channels", 0) > 0:
                    self.mic_combo.addItem(d["name"])
        except Exception:
            pass
        saved_mic = self.settings.get("mic_device", "")
        if saved_mic:
            i = self.mic_combo.findText(saved_mic)
            if i >= 0:
                self.mic_combo.setCurrentIndex(i)
        self.mic_combo.currentIndexChanged.connect(self._on_mic_changed)
        ll.addWidget(self.mic_combo, 1)
        body.addWidget(left, 1)

        right, rl = self._settings_cell()
        rl.addWidget(self._set_text_block("Авто-отправка (Enter)",
                                          "Отправляет текст после окончания записи"))
        rl.addStretch()
        self.auto_send_toggle = ToggleSwitch(checked=self.settings.get("auto_send"))
        self.auto_send_toggle.toggled.connect(self.on_auto_send_toggled)
        rl.addWidget(self.auto_send_toggle)
        body.addWidget(right, 1)
        grid.addWidget(row)

        grid.addStretch(1)
        group.set_content(content)
        lay.addWidget(group)

        self._on_mic_changed()
        self._apply_cloud_settings()

    def _input_style(self):
        return ("QLineEdit { color: #00ff88; background: transparent;"
                " border: 1px solid rgba(0,255,136,0.3); border-radius: 4px;"
                " font: bold 11px 'Segoe UI'; padding: 0 6px; }")

    def _pick_cloud_color(self, key, default):
        dlg = QColorDialog(QColor(self.settings.get(key, default)), self)
        dlg.setWindowTitle("Цвет облачка")
        # подписи внутри палитры — тёмно-серые, читаемые
        dlg.setStyleSheet(
            "QLabel { color: #3c3c3c; }"
            "QPushButton { color: #222222; }"
            "QLineEdit { color: #222222; background: #ffffff; }"
            "QSpinBox { color: #222222; background: #ffffff; }"
            "QCheckBox { color: #3c3c3c; }")
        if dlg.exec():
            col = dlg.selectedColor()
            if col.isValid():
                self.settings.set(key, col.name())
                self._apply_cloud_settings()

    def _toggle_cloud(self, checked):
        self.settings.set("cloud_enabled", bool(checked))
        self._apply_cloud_settings()
        # капсула и облачко меняются местами: включено — волна в облачке
        if self.recorder.is_recording:
            if checked:
                self.waveform.hide_wave()
            else:
                self.waveform.show_recording()

    def _on_mic_changed(self):
        """Выбор микрофона: программа использует его напрямую, без настроек Windows."""
        name = self.mic_combo.currentText() if self.mic_combo else ""
        dev = None
        if name and name != "(системный по умолчанию)":
            try:
                import sounddevice as _sd
                for i, d in enumerate(_sd.query_devices()):
                    if d.get("max_input_channels", 0) > 0 and d["name"] == name:
                        dev = i
                        break
            except Exception:
                dev = None
            self.settings.set("mic_device", name)
        else:
            self.settings.set("mic_device", "")
        self.recorder.device = dev
        log("MIC_SELECTED", f"{name or 'default'} -> device={dev}")

    def _open_vocabulary_folder(self):
        """Открыть папку vocabularies — туда кладутся текстовые файлы словарей."""
        from vocabulary.manager import VocabularyManager
        try:
            manager = self.transcriber.vocabulary if self.transcriber else VocabularyManager()
            path = manager.vocab_dir
            os.makedirs(path, exist_ok=True)
            os.startfile(path)          # открывается Проводник Windows
            log("VOCAB_FOLDER", path)
        except Exception as e:
            log("VOCAB_FOLDER_ERROR", str(e))

    def _reload_vocabulary(self):
        """Словарь изменился — обновить буст слов в модели (в фоне)."""
        try:
            if self.transcriber:
                threading.Thread(target=self.transcriber.reload_vocabulary, daemon=True).start()
        except Exception:
            pass

    def _apply_cloud_settings(self):
        try:
            size = int(self.cloud_font_size.currentText())
        except Exception:
            size = 16
        size = max(8, min(18, size))
        # фокус с настроек убираем — чтобы диктовка не «влетала» в поля
        try:
            f = QApplication.focusWidget()
            if f is not None:
                f.clearFocus()
        except Exception:
            pass
        opacity = int(self.cloud_opacity.value()) if self.cloud_opacity else 100
        fam = self.cloud_font_name.currentText() if self.cloud_font_name else ""
        if fam == "(по умолчанию)":
            fam = ""
        self.settings.set("cloud_font", size)
        self.settings.set("cloud_opacity", opacity)
        self.settings.set("cloud_font_name", fam)
        self.stream_overlay.apply_style(
            self.settings.get("cloud_bg", "#ececec"),
            self.settings.get("cloud_fg", "#5c5c5c"),
            size,
            opacity,
            fam)
        self.stream_overlay.set_enabled(self.settings.get("cloud_enabled", True))

    def _paint_cube_logo(self, widget, event):
        p = QPainter(widget)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#1c1c1c"), 1.5))
        p.setBrush(QBrush(QColor(28, 28, 28, 30)))
        p.drawPolygon(QPolygonF([QPointF(16, 2), QPointF(30, 9), QPointF(16, 16), QPointF(2, 9)]))
        p.setBrush(QBrush(QColor(28, 28, 28, 15)))
        p.drawPolygon(QPolygonF([QPointF(2, 9), QPointF(16, 16), QPointF(16, 30), QPointF(2, 23)]))
        p.setBrush(QBrush(QColor(28, 28, 28, 20)))
        p.drawPolygon(QPolygonF([QPointF(30, 9), QPointF(16, 16), QPointF(16, 30), QPointF(30, 23)]))
        p.end()

    def _paint_checkmark(self, widget, event):
        p = QPainter(widget)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#00ff88"), 2))
        p.drawLine(2, 7, 5, 11)
        p.drawLine(5, 11, 12, 2)
        p.end()

    def _paint_header_btn(self, widget, event, icon_type):
        p = QPainter(widget)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = widget.width()
        is_hover = widget.underMouse()
        border_color = QColor("#00ff88") if is_hover else QColor("#555")
        icon_color = QColor("#00ff88") if is_hover else QColor("#aaa")
        p.setPen(QPen(border_color, 1))
        p.setBrush(QBrush(QColor(255, 255, 255, 5)))
        p.drawEllipse(1, 1, s - 2, s - 2)
        p.setPen(QPen(icon_color, 1.5))
        cx, cy = s // 2, s // 2
        if icon_type == "minimize":
            p.drawLine(cx - 5, cy, cx + 5, cy)
        elif icon_type == "close":
            p.drawLine(cx - 4, cy - 4, cx + 4, cy + 4)
            p.drawLine(cx + 4, cy - 4, cx - 4, cy + 4)
        elif icon_type == "help":
            font = QFont("Segoe UI", 13, QFont.Weight.Bold)
            p.setFont(font)
            p.drawText(widget.rect(), Qt.AlignmentFlag.AlignCenter, "?")
        p.end()

    def _create_mode_panel(self, subtitle, title, desc, active):
        # на бирке текст заглавными (макет v3), внутри — свои подписи
        panel = GroupBox(subtitle.upper(), active=active)
        panel.setCursor(Qt.CursorShape.PointingHandCursor)
        panel._active = active

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        icon_container = QWidget()
        icon_container.setFixedSize(50, 50)
        icon_container._is_hold = "HOLD" in subtitle.upper()
        icon_container.setStyleSheet(f"""
            border: 1px solid {'#1c1c1c' if active else '#e2e2de'};
            border-radius: 25px;
            background: #ffffff;
        """)
        icon_container.paintEvent = lambda e, ic=icon_container, at=active: self._paint_mode_icon(ic, e, at)
        icon_container._is_hold = "HOLD" in subtitle.upper()
        panel._icon_container = icon_container
        layout.addWidget(icon_container, alignment=Qt.AlignmentFlag.AlignHCenter)

        sub = QLabel(subtitle.upper())
        sub.setStyleSheet(f"color: {'#000' if active else '#777'}; font: bold 10px 'Segoe UI'; background: transparent; border: none;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        t = QLabel(title)
        t.setStyleSheet("color: #00c25a; font: 11px 'Segoe UI'; background: transparent; border: none;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(t)

        d = QLabel(desc)
        d.setWordWrap(True)
        d.setStyleSheet("color: #222; font-size: 11px; background: transparent; border: none;")
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(d)

        layout.insertStretch(0)   # содержимое центрируется по вертикали, как в макете — подписи идут плотно
        layout.addStretch()
        panel.set_content(content)
        panel.mousePressEvent = lambda e, p=panel, s=subtitle: self._on_panel_click(p, s)
        panel._title_label = t
        panel._subtitle_label = sub
        return panel

    def _update_panel_style(self, panel, active):
        panel.set_active(active)

    def _paint_mode_icon(self, widget, event, active):
        p = QPainter(widget)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = "#1c1c1c" if active else "#555"
        p.setPen(QPen(QColor(color), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = widget.width() // 2, widget.height() // 2
        is_hold = getattr(widget, '_is_hold', True)
        if is_hold:
            p.drawRoundedRect(cx - 6, cy - 8, 12, 10, 2, 2)
            p.drawRoundedRect(cx - 8, cy + 2, 16, 6, 2, 2)
            p.drawEllipse(cx - 2, cy - 4, 4, 4)
        else:
            p.drawRoundedRect(cx - 10, cy - 4, 20, 8, 4, 4)
            p.setBrush(QBrush(QColor(color)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(cx + 2, cy - 2, 4, 4)
        p.end()

    def _on_panel_click(self, panel, subtitle):
        is_hold = "Hold" in subtitle
        mode = "hold" if is_hold else "toggle"
        self.settings.set("mode", mode)
        try:
            import winsound
            wav = os.path.join(get_base_dir(), "sounds", "ping.wav")
            if os.path.exists(wav):
                winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except:
            pass
        if hasattr(self, 'mode_combo'):
            self.mode_combo.setCurrentIndex(0 if is_hold else 1)
        self.hold_panel._active = is_hold
        self.toggle_panel._active = not is_hold
        self._update_panel_style(self.hold_panel, is_hold)
        self._update_panel_style(self.toggle_panel, not is_hold)
        self._update_panel_texts(self.hold_panel, is_hold)
        self._update_panel_texts(self.toggle_panel, not is_hold)

    def _update_panel_texts(self, panel, active):
        color = "#000" if active else "#777"
        panel._subtitle_label.setStyleSheet(f"color: {color}; font: bold 10px 'Segoe UI'; background: transparent; border: none;")
        panel._title_label.setStyleSheet("color: #00c25a; font: 11px 'Segoe UI'; background: transparent; border: none;")
        icon_container = panel._icon_container
        icon_container.setStyleSheet(f"""
            border: 1px solid {'#1c1c1c' if active else '#e2e2de'};
            border-radius: 25px;
            background: #ffffff;
        """)
        icon_container.paintEvent = lambda e, ic=icon_container, at=active: self._paint_mode_icon(ic, e, at)
        icon_container.update()

    def _create_center_widget(self):
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._circle_widget = QWidget()
        self._circle_widget.setFixedSize(200, 200)
        self._circle_widget.setStyleSheet("background: transparent;")
        self._signal_level = 76
        self._circle_widget.paintEvent = lambda e: self._paint_circle(self._circle_widget, e)
        layout.addWidget(self._circle_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        self._mascot_label = QLabel()
        mascot_path = os.path.join(get_base_dir(), "mascot_new.png")
        if not os.path.exists(mascot_path):
            mascot_path = os.path.join(get_base_dir(), "mascot.png")
        if os.path.exists(mascot_path):
            self._mascot_label.setPixmap(QPixmap(mascot_path).scaled(112, 112, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self._mascot_label.setText("\U0001f916")
            self._mascot_label.setStyleSheet("font-size: 48px; background: transparent; border: none;")
        self._mascot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mascot_label.setParent(self._circle_widget)
        self._mascot_label.setFixedSize(112, 112)
        self._mascot_label.move(46, 24)

        sig_label = QLabel("УРОВЕНЬ СИГНАЛА")
        sig_label.setStyleSheet("color: #333; font-size: 10px; letter-spacing: 2px; background: transparent; border: none;")
        sig_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sig_label.setParent(self._circle_widget)
        sig_label.setFixedSize(180, 14)
        sig_label.move(11, 130)

        self._signal_value_label = QLabel(f"{self._signal_level}%")
        self._signal_value_label.setStyleSheet("color: #00c25a; font: bold 28px 'Segoe UI'; background: transparent; border: none;")
        self._signal_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._signal_value_label.setParent(self._circle_widget)
        self._signal_value_label.setFixedSize(180, 36)
        self._signal_value_label.move(11, 140)

        self._signal_timer = QTimer()
        self._signal_timer.timeout.connect(self._update_signal)
        self._signal_timer.start(1500)

        return GroupBox("Уровень сигнала", widget)

    def _paint_circle(self, widget, event):
        p = QPainter(widget)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = widget.width(), widget.height()
        cx, cy, r = w // 2, h // 2, 90
        r2 = r - 4 - 3

        # круглый фон под маскотом — .level-inner из макета: чуть темнее панели,
        # радиальный градиент со светлым верхом (#f4f4f2 → #eaeae7)
        grad = QRadialGradient(cx, cy - r2 * 0.24, float(r2))
        grad.setColorAt(0.0, QColor("#f4f4f2"))
        grad.setColorAt(0.75, QColor("#eaeae7"))
        grad.setColorAt(1.0, QColor("#eaeae7"))
        p.setPen(QPen(QColor("#e4e4e0"), 1))
        p.setBrush(QBrush(grad))
        p.drawEllipse(cx - r2, cy - r2, r2 * 2, r2 * 2)

        pen_track = QPen(QColor(226, 226, 222), 3)
        p.setPen(pen_track)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        span = int(360 * 16 * self._signal_level / 100)
        pen_active = QPen(QColor("#00c25a"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen_active)
        p.drawArc(cx - r, cy - r, r * 2, r * 2, 90 * 16, -span)

        if self.is_recording:
            pen_inner = QPen(QColor("#00c25a"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen_inner)
            p.drawEllipse(cx - r2, cy - r2, r2 * 2, r2 * 2)
            glow = QColor(0, 194, 90, 30)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(glow))
            p.drawEllipse(cx - r2 - 4, cy - r2 - 4, r2 * 2 + 8, r2 * 2 + 8)
        else:
            pen_inner = QPen(QColor(228, 228, 224), 2)
            p.setPen(pen_inner)
            p.drawEllipse(cx - r2, cy - r2, r2 * 2, r2 * 2)

        p.end()

    def _update_signal(self):
        self._signal_level = max(20, min(95, self._signal_level + int((0.5 - 0.5) * 8)))
        import random
        self._signal_level = max(20, min(95, self._signal_level + random.randint(-4, 4)))
        self._signal_value_label.setText(f"{self._signal_level}%")
        self._circle_widget.update()

    def _paint_neon_line(self, widget, event):
        painter = QPainter(widget)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = widget.width()
        h = widget.height()
        mid = w / 2
        r, g, b = 0, 247, 255
        fade_start = 0.32
        pen = QPen(QColor(r, g, b, 255), 2)
        painter.setPen(pen)
        painter.drawLine(int(w * fade_start), h // 2, int(w * (1 - fade_start)), h // 2)
        for i in range(30):
            t = i / 30
            alpha = int(255 * (1 - t))
            seg = int(w * fade_start / 30)
            x1l = int(w * fade_start) - int(w * fade_start * t)
            x2l = int(w * fade_start) - int(w * fade_start * (t + 1 / 30))
            x1r = int(w * (1 - fade_start)) + int(w * fade_start * t)
            x2r = int(w * (1 - fade_start)) + int(w * fade_start * (t + 1 / 30))
            pen = QPen(QColor(r, g, b, alpha), 2)
            painter.setPen(pen)
            painter.drawLine(x2l, h // 2, x1l, h // 2)
            painter.drawLine(x1r, h // 2, x2r, h // 2)
        painter.end()

    def init_ad_timer(self):
        self.ad_timer = QTimer()
        self.ad_timer.timeout.connect(self.check_ads)
        self.ad_timer.start(60000)

    def _paint_neon_active(self, widget, event):
        painter = QPainter(widget)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = widget.width()
        h = widget.height()
        color = QColor(widget._color)
        r, g, b = color.red(), color.green(), color.blue()
        fade_start = 0.32
        pen = QPen(QColor(r, g, b, 255), 2)
        painter.setPen(pen)
        painter.drawLine(int(w * fade_start), h // 2, int(w * (1 - fade_start)), h // 2)
        for i in range(30):
            t = i / 30
            alpha = int(255 * (1 - t))
            x1l = int(w * fade_start) - int(w * fade_start * t)
            x2l = int(w * fade_start) - int(w * fade_start * (t + 1 / 30))
            x1r = int(w * (1 - fade_start)) + int(w * fade_start * t)
            x2r = int(w * (1 - fade_start)) + int(w * fade_start * (t + 1 / 30))
            pen = QPen(QColor(r, g, b, alpha), 2)
            painter.setPen(pen)
            painter.drawLine(x2l, h // 2, x1l, h // 2)
            painter.drawLine(x1r, h // 2, x2r, h // 2)
        painter.end()

    def init_waveform(self):
        self.waveform = WaveformWindow()

    def check_ads(self):
        if self.ad_manager.should_show():
            self.show_tray_ad()
            self.ad_manager.mark_shown()

    def show_tray_ad(self):
        config = self.ad_manager.get_tray_config()
        if config:
            self.tray.showMessage(
                config.get("title", "Talker Box"),
                config.get("message", ""),
                QSystemTrayIcon.MessageIcon.Information,
                10000
            )

    def init_tray(self):
        self.tray = QSystemTrayIcon(self)
        icon_path = os.path.join(get_base_dir(), "talker_box.png")
        if os.path.exists(icon_path):
            self.tray.setIcon(QIcon(icon_path))
        else:
            self.tray.setIcon(self.create_mic_icon("#00f7ff"))

        tray_menu = QMenu()

        settings_action = QAction("Настройки", self)
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addAction(settings_action)

        help_action = QAction("Справка", self)
        help_action.triggered.connect(self._open_help)
        tray_menu.addAction(help_action)

        tray_menu.addSeparator()

        toggle_action = QAction("Вкл/Выкл запись", self)
        toggle_action.triggered.connect(self.toggle_recording)
        tray_menu.addAction(toggle_action)

        tray_menu.addSeparator()

        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()

    def create_mic_icon(self, color):
        base = QPixmap(64, 64)
        base.fill(Qt.GlobalColor.transparent)
        p = QPainter(base)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(122, 122, 118)))
        p.drawEllipse(4, 4, 56, 56)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(color), 3))
        p.drawEllipse(5, 5, 54, 54)
        p.setPen(Qt.PenStyle.NoPen)
        icon_path = os.path.join(get_base_dir(), "talker_box.png")
        if os.path.exists(icon_path):
            icon_pixmap = QPixmap(icon_path).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            x = (64 - 48) // 2
            y = (64 - 48) // 2
            p.drawPixmap(x, y, icon_pixmap)
        p.end()
        return QIcon(base)

    def init_hotkey(self):
        self._last_toggle_time = 0
        hotkey = self.settings.get("hotkey", "f9")
        self._start_listener(hotkey)

    def _start_listener(self, hotkey):
        self._stop_listener()
        try:
            self._hotkey_listener = HotkeyListener(
                hotkey,
                on_down=lambda: self._hotkey_signal.emit("DOWN"),
                on_up=lambda: self._hotkey_signal.emit("UP"),
                on_escape=lambda: self._hotkey_signal.emit("ESC"),
            )
            self._hotkey_listener.start()
            self._set_esc(self.is_recording or self._has_pending_text())
            print(f"Hotkey listener: {hotkey}")
        except Exception as e:
            print(f"Listener error: {e}")

    def _stop_listener(self):
        if self._hotkey_listener:
            self._hotkey_listener.stop()
            self._hotkey_listener = None

    def _restart_listener(self):
        self._stop_listener()
        hotkey = self.settings.get("hotkey", "ctrl+win")
        self._start_listener(hotkey)

    def _on_hotkey_event(self, event):
        if event == "ESC":
            self.cancel_session()      # Escape = крестик в облачке (отмена диктовки/текста)
            return
        if self._suppress_hotkey:
            log("HOTKEY_SUPPRESSED", event)
            return

        if event == "DOWN":
            now = time.time()
            if now - self._last_toggle_time < 0.5:
                log("HOTKEY_BLOCKED", f"debounce {now - self._last_toggle_time:.2f}s")
                return
            self._last_toggle_time = now
            log("HOTKEY_DOWN", f"mode={self.settings.get('mode')} recording={self.is_recording}")

            mode = self.settings.get("mode")
            if mode == "toggle":
                if self.is_recording:
                    self.stop_recording()
                elif self._has_pending_text():
                    self.send_pending()
                else:
                    self.start_recording()
            else:
                if not self.is_recording:
                    if self._has_pending_text():
                        self.send_pending()     # текст висит в облачке — хоткей его отправляет
                    else:
                        self.start_recording()
                        self.hold_mode = True

        elif event == "UP":
            log("HOTKEY_UP", f"mode={self.settings.get('mode')} hold={self.hold_mode} recording={self.is_recording}")
            mode = self.settings.get("mode")
            if mode == "hold" and self.hold_mode and self.is_recording:
                self.hold_mode = False
                self.stop_recording()

    def start_recording(self):
        if not self.is_recording:
            if hasattr(self, '_recording_timeout') and self._recording_timeout:
                self._recording_timeout.stop()
                self._recording_timeout = None
            log("RECORD_START", f"mode={self.settings.get('mode')}")
            self.is_recording = True
            self._target_hwnd = self._last_foreign or self._foreground_hwnd()   # окно, куда уйдёт текст
            self._recording_start_time = time.monotonic()
            self.phrase_stream.transcriber = self.transcriber
            self.phrase_stream.start()
            # доставка текста — ТОЛЬКО через сигнал (из фонового потока в окно напрямую нельзя!)
            self.phrase_stream.on_phrase = lambda t, p=False: self.signals.stream_phrase.emit(t, p)
            self._stream_epoch += 1
            self._stream_committed = ""
            self._pending_send = False
            self._cloud_edited = False
            self._cloud_touched = False    # новая диктовка — облачко ещё не трогали
            self._keep_for_edit = False
            self._session_fixes = []       # правки словаря, сделанные по ходу этой диктовки
            self.stream_overlay.capture_anchor()   # облачко закрепляется у поля ввода
            self.stream_overlay.set_send_visible(True)   # кнопка «Отправить» — на время диктовки
            self._set_esc(True)    # Escape отменяет диктовку, как крестик
            self.recorder.stream_hook = self.phrase_stream.feed
            self.recorder.start()
            self._ignore_text = False   # новая диктовка — её текст вставлять можно
            if self.settings.get("cloud_enabled", True):
                self.waveform.hide_wave()   # волна живёт в облачке
                self.stream_overlay.show_idle()   # сразу после хоткея — спокойная волна, облачко потом
            else:
                self.waveform.show_recording()
            self.signals.recording_started.emit()
            play_start_sound()
            self._recording_session = getattr(self, '_recording_session', 0) + 1
            session = self._recording_session
            self._recording_timeout = QTimer.singleShot(300000, lambda s=session: self._on_recording_timeout(s))

    def _on_recording_timeout(self, session):
        if session == getattr(self, '_recording_session', 0):
            self._force_stop_recording()

    def _force_stop_recording(self):
        if self.is_recording:
            elapsed = time.monotonic() - getattr(self, '_recording_start_time', 0)
            log("RECORD_TIMEOUT", f"300s limit reached (elapsed={elapsed:.1f}s)")
            self._recording_timeout = None
            self.stop_recording()

    def _on_send_click(self):
        """Кнопка «Отправить»: звук-подтверждение и отправка того, что в облачке."""
        log("SEND_CLICK", "кнопка «Отправить»")
        try:
            import winsound
            wav = os.path.join(get_base_dir(), "sounds", "ping.wav")
            if os.path.exists(wav):
                winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            pass
        if self.is_recording:
            self.stop_recording()      # ещё диктуем — сначала остановиться
        elif self._has_pending_text():
            self.send_pending()        # текст уже готов — отправить его

    def _has_pending_text(self):
        """В облачке лежит текст, который можно отправить (не важно, pending он или нет)."""
        try:
            if not self.stream_overlay.isVisible():
                return False
            return bool((self.stream_overlay.label.text() or "").strip())
        except Exception:
            return False

    def _cloud_mouse_selected(self):
        """Выделен ли сейчас в облачке фрагмент текста мышкой."""
        try:
            return bool((self.stream_overlay.label.selectedText() or "").strip())
        except Exception:
            return False

    def _set_esc(self, on):
        """Ловить Escape (отмена распознавания) — только пока идёт сессия."""
        try:
            if self._hotkey_listener:
                self._hotkey_listener.esc_enabled = bool(on)
        except Exception:
            pass

    def cancel_session(self):
        """Escape или крестик: отменить диктовку либо убрать готовый текст из облачка."""
        if self.is_recording or getattr(self.recorder, "is_recording", False):
            log("CANCEL", "отмена диктовки (Escape/крестик)")
            self._stream_reset()
            return
        if not self.stream_overlay.isVisible():
            self._set_esc(False)
            return
        log("CANCEL", "убрать текст из облачка (Escape/крестик)")
        self._pending_send = False
        self._cloud_edited = False
        self._stream_committed = ""
        self._set_esc(False)
        self.stream_overlay.hide()
        self.stream_overlay.clear_anchor()

    def send_pending(self):
        """Отправить текст из облачка — ровно в том виде, в каком его оставил пользователь."""
        text = ""
        try:
            text = (self.stream_overlay.label.text() or "").strip()
        except Exception:
            text = ""
        text = text or (self._stream_committed or "").strip()
        self._pending_send = False
        if not text:
            log("SEND_PENDING", "пусто — нечего отправлять")
            self.stream_overlay.hide()
            self.stream_overlay.clear_anchor()
            return
        log("SEND_PENDING", f"len={len(text)}")
        self._suppress_hotkey = True
        self.phrase_stream.on_phrase = None   # запоздалые куски не перерисуют облачко
        self._stream_epoch += 1               # и не вставятся после отправки
        # цель: активное чужое окно; если сверху наши (облачко/панель) —
        # последнее чужое окно, в котором пользователь реально работал
        self._target_hwnd = self._resolve_target()
        log("SEND_TARGET", self._hwnd_desc(self._target_hwnd))
        self.recorder.stream_hook = None
        self._do_paste(text)

    @staticmethod
    def _is_foreign(hwnd):
        """Окно принадлежит другому процессу (не Talker Box)?"""
        try:
            import ctypes
            from ctypes import wintypes
            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return pid.value not in (0, os.getpid())
        except Exception:
            return False

    def _update_last_foreign(self):
        """Запомнить последнее активное чужое окно — это цель для вставки."""
        try:
            hwnd = self._foreground_hwnd()
            if hwnd and self._is_foreign(hwnd):
                self._last_foreign = hwnd
        except Exception:
            pass

    def _resolve_target(self):
        """Куда печатать: текущее чужое окно, иначе последнее чужое."""
        fg = self._foreground_hwnd()
        if fg and self._is_foreign(fg):
            self._last_foreign = fg
            return fg
        return self._last_foreign or getattr(self, "_target_hwnd", 0)

    def _on_add_word_request(self, selected):
        """Выделенное слово из облачка → форма «Добавить в словарь»."""
        wrong = (selected or "").strip()
        if not wrong:
            return
        self._cloud_touched = True   # правим словарь — текст ждёт
        from PyQt6.QtWidgets import QDialog, QLineEdit, QPushButton
        from vocabulary.manager import VocabularyManager

        dlg = QDialog(self)
        dlg.setWindowTitle("Добавить в словарь")
        dlg.setStyleSheet(
            "QDialog { background: #ffffff; }"
            "QLabel { color: #333333; font-size: 12px; background: transparent; border: none; }"
            "QLineEdit { color: #222222; background: #ffffff; border: 1px solid #bbbbbb;"
            " border-radius: 4px; padding: 3px 6px; font-size: 12px; }"
            "QPushButton { color: #ffffff; background: #2e8b75; border: none;"
            " border-radius: 6px; padding: 5px 16px; font-size: 12px; }"
            "QPushButton:hover { background: #14b89a; }")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(8)
        lay.addWidget(QLabel("Неправильно (так написала модель):"))
        wrong_edit = QLineEdit(wrong)
        wrong_edit.setReadOnly(True)
        lay.addWidget(wrong_edit)
        lay.addWidget(QLabel("Правильное слово (писать руками):"))
        right_edit = QLineEdit()
        lay.addWidget(right_edit)
        lay.addWidget(QLabel("Ещё варианты ошибок (через запятую, необязательно):"))
        more_edit = QLineEdit()
        lay.addWidget(more_edit)
        buttons = QHBoxLayout()
        buttons.addStretch()
        ok_btn = QPushButton("Добавить")
        cancel_btn = QPushButton("Отмена")
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        lay.addLayout(buttons)
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        right_edit.setFocus()

        self._set_esc(False)      # в диалоге Escape закрывает диалог, а не сессию
        accepted = dlg.exec()
        self._set_esc(self.is_recording or self._has_pending_text())
        if not accepted:
            return
        target = right_edit.text().strip()
        if not target:
            return
        variants = [wrong] + [v.strip() for v in more_edit.text().split(",") if v.strip()]
        try:
            manager = self.transcriber.vocabulary if self.transcriber else VocabularyManager()
            manager.add_word(target, variants)
            log("VOCAB_ADD", f"{wrong!r} -> {target!r}")
            self._reload_vocabulary()
        except Exception as e:
            log("VOCAB_ADD_ERROR", str(e))
        # слово исправляется сразу в тексте облачка
        try:
            fixed = self.stream_overlay.replace_in_text(wrong, target)
            if fixed:
                self._stream_committed = fixed
                self._cloud_edited = True   # правки в облачке — финальный ASR их не затрёт
        except Exception:
            pass
        # запоминаем правку на всю диктовку: применяется и к финальному тексту ASR
        try:
            if not hasattr(self, "_session_fixes"):
                self._session_fixes = []
            self._session_fixes.append((wrong, target))
        except Exception:
            pass

    def _apply_session_fixes(self, text):
        """Применить к тексту правки словаря, сделанные по ходу диктовки."""
        import re
        for wrong, target in list(getattr(self, "_session_fixes", []) or []):
            if not wrong or not target or wrong == target:
                continue
            try:
                text = re.sub(r"(?<!\w)" + re.escape(wrong) + r"(?!\w)",
                              target, text, flags=re.IGNORECASE)
            except Exception:
                continue
        return text

    def stop_recording(self):
        if self.is_recording:
            if hasattr(self, '_recording_timeout') and self._recording_timeout:
                self._recording_timeout.stop()
                self._recording_timeout = None
            self.recorder.stream_hook = None
            audio = self.recorder.stop()
            frames = len(audio) if len(audio) > 0 else 0
            duration = frames / 16000 if frames > 0 else 0
            log("RECORD_STOP", f"frames={frames} duration={duration:.1f}s")
            self.is_recording = False
            # ждущего режима нет: остановка всегда отправляет текст сама,
            # правки, сделанные по ходу диктовки, подхватятся при вставке
            self._keep_for_edit = False
            self._pending_send = False
            log("STOP_SEND", f"touched={self._cloud_touched} edited={self._cloud_edited}")
            self.signals.recording_stopped.emit()
            self.waveform.hide_wave()
            self.stream_overlay.set_wave_active(False)   # волна гаснет — речи больше нет
            self.stream_overlay.set_send_visible(False)
            play_stop_sound()
            self.signals.transcribing_started.emit()
            threading.Thread(target=self.transcribe_audio, args=(audio,), daemon=True).start()

    def _check_rmb_reset(self):
        """Следит за облачком: таймер диктовки, крестик сброса, правая кнопка — сброс."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            self._update_last_foreign()   # запоминаем окно, в котором работает пользователь

            # таймер диктовки и волна в облачке
            if self.recorder.is_recording:
                el = int(time.monotonic() - getattr(self, "_recording_start_time", time.monotonic()))
                t = "%d:%02d" % (el // 60, el % 60)
                if t != getattr(self, "_last_time_text", ""):
                    self._last_time_text = t
                    self.stream_overlay.set_time(t)
                # волна слушает голос: речь — играет, тишина — гаснет
                self.stream_overlay.set_wave_active(self.phrase_stream.is_speech)

            # левая кнопка на крестике облачка — сброс; ловим даже короткие клики
            # (0x0001 = «кнопка нажималась с прошлого опроса» — ничего не проскакивает)
            st = user32.GetAsyncKeyState(0x01)
            down = bool(st & 0x8000)
            clicked = (down and not getattr(self, "_lmb_was_down", False)) or bool(st & 0x0001)
            self._lmb_was_down = down
            if clicked and self.stream_overlay.isVisible():
                x, y = self._cursor_xy()
                # клик по облачку = пользователь с ним работает (выделяет слово,
                # открывает меню словаря) — после остановки текст будет ждать правок
                try:
                    dpr = self.stream_overlay.devicePixelRatioF() or 1.0
                    g = self.stream_overlay.geometry()
                    lx, ly = x / dpr, y / dpr
                    if g.left() <= lx <= g.right() and g.top() <= ly <= g.bottom():
                        if not self._cloud_touched:
                            log("CLOUD_TOUCHED", "клик по облачку — текст будет ждать правок")
                        self._cloud_touched = True
                except Exception:
                    pass
                crect = self.stream_overlay.close_rect()
                if crect and self._in_rect(x, y, crect):
                    self.cancel_session()   # крестик = то же, что Escape

            # правая кнопка по облачку — меню словаря (тоже «трогали мышкой»)
            if user32.GetAsyncKeyState(0x02) & 0x8001 and self.stream_overlay.isVisible():
                x, y = self._cursor_xy()
                try:
                    dpr = self.stream_overlay.devicePixelRatioF() or 1.0
                    g = self.stream_overlay.geometry()
                    lx, ly = x / dpr, y / dpr
                    if g.left() <= lx <= g.right() and g.top() <= ly <= g.bottom():
                        self._cloud_touched = True
                except Exception:
                    pass

        except Exception as e:
            log("CLICK_CHECK_ERROR", str(e))

    def _cursor_xy(self):
        import ctypes

        class P(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        p = P()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
        return p.x, p.y

    @staticmethod
    def _in_rect(x, y, r):
        """Координата внутри прямоугольника (r = x, y, w, h)."""
        rx, ry, rw, rh = r
        return rx <= x <= rx + rw and ry <= y <= ry + rh

    @staticmethod
    def _foreground_hwnd():
        """Дескриптор активного окна (куда смотрит пользователь)."""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = wintypes.HWND
            return int(user32.GetForegroundWindow() or 0)
        except Exception:
            return 0

    @staticmethod
    def _hwnd_desc(hwnd):
        """Для лога: '0x1234 «Заголовок окна»'."""
        try:
            import ctypes
            if not hwnd:
                return "0"
            buf = ctypes.create_unicode_buffer(160)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, 160)
            return f"0x{hwnd:X} «{buf.value[:60]}»"
        except Exception:
            return str(hwnd)

    def _focus_target(self):
        """Вернуть фокус в окно назначения. True — окно активно и можно печатать.

        Облачко и его кнопка — отдельные окна: после клика по ним фокус остаётся
        у нас, и символы SendInput уходят «в никуда». Поэтому окно назначения
        поднимаем через AttachThreadInput (обход системного запрета на смену
        активного окна) и возвращаем фокус тому же элементу внутри него.
        """
        try:
            import ctypes
            from ctypes import wintypes

            class _RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            class _GTI(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                    ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                    ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                    ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                    ("rcCaret", _RECT),
                ]

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            hwnd = getattr(self, "_target_hwnd", 0)
            if not hwnd or not user32.IsWindow(hwnd):
                log("FOCUS_FAIL", f"окно назначения не найдено hwnd={hwnd}")
                return False
            if user32.GetForegroundWindow() == hwnd:
                return True

            my_tid = kernel32.GetCurrentThreadId()
            tgt_tid = user32.GetWindowThreadProcessId(hwnd, None)
            attached = False
            try:
                if tgt_tid and tgt_tid != my_tid:
                    attached = bool(user32.AttachThreadInput(my_tid, tgt_tid, True))
                # Alt — снимает системный запрет на смену активного окна
                user32.keybd_event(0x12, 0, 0, 0)
                user32.keybd_event(0x12, 0, 2, 0)
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.SetActiveWindow(hwnd)
                # фокус — тому же элементу внутри окна (поле ввода)
                gti = _GTI()
                gti.cbSize = ctypes.sizeof(_GTI)
                if user32.GetGUIThreadInfo(tgt_tid, ctypes.byref(gti)) and gti.hwndFocus:
                    if user32.IsWindow(gti.hwndFocus):
                        user32.SetFocus(gti.hwndFocus)
            finally:
                if attached:
                    user32.AttachThreadInput(my_tid, tgt_tid, False)

            fg = user32.GetForegroundWindow()
            ok = (fg == hwnd) or (user32.GetAncestor(fg, 2) == hwnd)   # GA_ROOT = 2
            log("FOCUS_TARGET", f"hwnd={hwnd} fg={fg} ok={ok}")
            return ok
        except Exception as e:
            log("FOCUS_ERROR", str(e))
            return False

    def _stream_reset(self):
        """Сброс: полная остановка сессии — новая диктовка только по хоткею заново."""
        log("STREAM_RESET", "сессия остановлена, ждём хоткей заново")
        play_reset_sound()
        self._stream_committed = ""
        self.recorder.stream_hook = None
        try:
            self.recorder.stop()
        except Exception:
            pass
        self.phrase_stream.reset()
        self.phrase_stream.on_phrase = None   # запоздалые куски больше не перерисуют облачко
        self._stream_epoch += 1
        self.is_recording = False    # цикл закрыт: следующий хоткей сразу начнёт НОВУЮ диктовку
        self.hold_mode = False
        if hasattr(self, '_recording_timeout') and self._recording_timeout:
            self._recording_timeout.stop()
            self._recording_timeout = None
        self._suppress_hotkey = False
        self._last_time_text = ""
        self._ignore_text = True   # запоздалый текст отменённой диктовки не вставляем
        self._pending_send = False
        self._cloud_edited = False
        self._set_esc(False)
        # буфер обмена не трогаем: он программе не нужен, а чужие картинки целы
        self.stream_overlay.set_wave_active(False)   # отмена — волна замирает
        self.stream_overlay.set_send_visible(False)
        self.stream_overlay.flash_reset("Сброшено — жмите хоткей заново")
        self.waveform.hide_wave()          # капсула индикации тоже гаснет
        self.signals.recording_stopped.emit()

    def _on_stream_phrase(self, text, partial=False):
        """Живой текст: слова появляются по мере речи; на паузе — точная фраза."""
        if not self.is_recording:
            return   # речь остановлена — запоздалые куски не должны перебивать правки
        if partial:
            shown = (self._stream_committed + " " + text).strip()
        else:
            self._stream_committed = (self._stream_committed + " " + text).strip()
            if len(self._stream_committed) > 600:
                self._stream_committed = self._stream_committed[-600:]
            shown = self._stream_committed
            # пауза — пересчитываем ВСЮ диктовку целиком (точно как уйдёт в поле)
            QTimer.singleShot(350, self._refresh_session_text)
        self.stream_overlay.show_text(shown)

    def _refresh_session_text(self):
        """Точный текст всей диктовки — тот же, что отправится в поле ввода."""
        try:
            if self._session_busy or not self.recorder.is_recording:
                return
            audio = self.recorder.get_audio()
            if len(audio) < 8000:   # меньше полсекунды речи — нечего пересчитывать
                return
            self._session_busy = True
            threading.Thread(target=self._session_asr, args=(audio, self._stream_epoch), daemon=True).start()
        except Exception as e:
            log("SESSION_REFRESH_ERROR", str(e))

    def _session_asr(self, audio, epoch):
        try:
            text = (self.transcriber.transcribe(audio) or "").strip()
            if text and epoch == getattr(self, "_stream_epoch", 0):
                self.signals.session_text.emit(text)
        except Exception as e:
            log("SESSION_ASR_ERROR", str(e))
        finally:
            self._session_busy = False

    def _on_session_text(self, text):
        """Показываем точный текст — ровно тот, что уйдёт в поле ввода."""
        if not self.is_recording:
            return   # сессия уже остановлена — её текст не перезаписываем
        self._stream_committed = text
        self.stream_overlay.show_text(text)

    def transcribe_audio(self, audio):
        elapsed = time.monotonic() - getattr(self, '_recording_start_time', time.monotonic())
        if elapsed > 305:   # лимит записи — 5 минут (300 с + запас)
            log("TRANSCRIBE_SKIP", f"stale audio from {elapsed:.1f}s ago")
            self.signals.transcribing_finished.emit()
            return
        if self.transcriber and len(audio) > 0:
            try:
                log("TRANSCRIBE_START", f"frames={len(audio)} elapsed={elapsed:.1f}s")
                text = self.transcriber.transcribe(audio)
                if not text:
                    # распознавание вернуло пусто — берём живой текст из облачка,
                    # чтобы надиктованное не пропало
                    live = (self._stream_committed or "").strip()
                    if live:
                        text = live
                        log("TRANSCRIBE_FALLBACK", "пустой результат — взят живой текст облачка")
                log("TRANSCRIBE_DONE", f"text={repr(text[:80]) if text else 'EMPTY'}")
                self.signals.transcribing_finished.emit()
                if text:
                    self.signals.text_ready.emit(text)
            except Exception as e:
                log("TRANSCRIBE_CRASH", str(e))
                self.signals.transcribing_finished.emit()
        else:
            reason = "no transcriber" if not self.transcriber else "empty audio"
            log("TRANSCRIBE_SKIP", reason)
            self.signals.transcribing_finished.emit()

    def on_text_ready(self, text):
        log("TEXT_READY", f"len={len(text)} text={repr(text[:60])}")
        if getattr(self, "_ignore_text", False):
            self._ignore_text = False
            self._suppress_hotkey = False
            log("TEXT_IGNORED", "диктовка была отменена — текст не вставляем")
            return
        # правки словаря, сделанные по ходу диктовки, применяем к финальному тексту
        text = self._apply_session_fixes(text)
        # правки по ходу диктовки (словарь/замена слова) главнее сырого ASR
        if self._cloud_edited and (self._stream_committed or "").strip():
            log("TEXT_USE_EDITED", "отправляем текст с правками из облачка")
            text = self._stream_committed
        # остановка всегда отправляет сразу: без ожидания и без пауз
        log("TEXT_PASTE_DIRECT", "вставляем сразу после остановки")
        self._pending_send = False
        self._suppress_hotkey = True
        QTimer.singleShot(100, lambda: self._do_paste(text))

    def _do_paste(self, text):
        try:
            # цель освежаем перед вставкой: активное чужое окно, иначе последнее рабочее
            self._target_hwnd = self._resolve_target()
            log("DO_PASTE", f"auto_send={self.settings.get('auto_send')} "
                            f"target={self._hwnd_desc(getattr(self, '_target_hwnd', 0))} "
                            f"fg={self._hwnd_desc(self._foreground_hwnd())}")
            if not self._focus_target():
                # фокус не вернулся — печатать некуда: текст остаётся в облачке
                log("PASTE_NO_TARGET", "фокус не вернулся — текст оставлен в облачке")
                self._pending_send = True
                try:
                    self.stream_overlay.set_time("нет окна")
                except Exception:
                    pass
                return
            time.sleep(0.12)   # окну нужно мгновение, чтобы стать активным
            is_terminal = _is_terminal()
            _paste_via_sendinput(text, auto_send=self.settings.get("auto_send"), is_terminal=is_terminal)
            log("DO_PASTE_DONE", "ok")
            # текст отправлен — облачко убираем, сессия закрыта
            self._pending_send = False
            self._cloud_edited = False
            self._stream_committed = ""
            self._set_esc(False)   # сессия закончена — Escape снова обычная клавиша
            self.stream_overlay.hide()
            self.stream_overlay.clear_anchor()
        except Exception as e:
            log("PASTE_ERROR", str(e))
        finally:
            QTimer.singleShot(300, self._release_hotkey_suppress)

    def _release_hotkey_suppress(self):
        self._suppress_hotkey = False

    def on_recording_started(self):
        self._circle_widget.update()
        self.tray.setIcon(self.create_mic_icon("#00ff88"))

    def on_recording_stopped(self):
        self._circle_widget.update()
        self.tray.setIcon(self.create_mic_icon("#f7ff00"))

    def on_transcribing_started(self):
        self.is_transcribing = True
        self.tray.setIcon(self.create_mic_icon("#00f7ff"))
        if not self.settings.get("cloud_enabled", True):
            self.waveform.show_transcribing()   # в режиме облачка капсула не нужна

    def on_transcribing_finished(self):
        self.is_transcribing = False
        self.waveform.hide_wave()
        icon_path = os.path.join(get_base_dir(), "talker_box.png")
        if os.path.exists(icon_path):
            self.tray.setIcon(QIcon(icon_path))
        else:
            self.tray.setIcon(self.create_mic_icon("#00f7ff"))

    def on_mode_changed(self, index):
        mode = "hold" if index == 0 else "toggle"
        self.settings.set("mode", mode)
    def on_auto_send_changed(self, state):
        self.settings.set("auto_send", state == Qt.CheckState.Checked.value)

    def on_auto_send_toggled(self, checked):
        self.settings.set("auto_send", checked)
        try:
            import winsound
            sound = "transition_up.wav" if checked else "transition_down.wav"
            wav = os.path.join(get_base_dir(), "sounds", sound)
            if os.path.exists(wav):
                winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except:
            pass

    def _format_hotkey(self, hotkey):
        modifier_order = {"ctrl": 0, "shift": 1, "alt": 2, "win": 3}
        parts = hotkey.split("+")
        parts.sort(key=lambda p: modifier_order.get(p.lower(), 99))
        return "+".join(p.capitalize() for p in parts)

    def start_hotkey_capture(self):
        self._stop_listener()
        self._capturing_hotkey = True
        self.hotkey_btn.setText("Нажмите клавишу")
        self.hotkey_btn.setStyleSheet(self._hotkey_btn_style(True))
        start_capture(self._on_hotkey_captured)

    def _on_hotkey_captured(self, combo):
        self._capturing_hotkey = False
        if combo:
            self.settings.set("hotkey", combo)
            self.hotkey_btn.setText(self._format_hotkey(combo))
            self.hotkey_btn.setStyleSheet(self._hotkey_btn_style())
            try:
                import winsound
                wav = os.path.join(get_base_dir(), "sounds", "transition_up.wav")
                if os.path.exists(wav):
                    winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except:
                pass
            QTimer.singleShot(100, lambda c=combo: self._start_listener(c))
        else:
            hotkey = self.settings.get("hotkey", "ctrl+win")
            self.hotkey_btn.setText(self._format_hotkey(hotkey))
            self.hotkey_btn.setStyleSheet(self._hotkey_btn_style())
            QTimer.singleShot(100, lambda h=hotkey: self._start_listener(h))

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def eventFilter(self, obj, event):
        return super().eventFilter(obj, event) if hasattr(super(), 'eventFilter') else False

    def keyPressEvent(self, event):
        return super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        return super().keyReleaseEvent(event)

    def load_active_model(self):
        from settings_manager import BUILTIN_MODEL
        from model_loader import ModelLoader
        model_path = os.path.join(get_exe_dir(), BUILTIN_MODEL["path"])
        model = dict(BUILTIN_MODEL, path=model_path)
        self._model_loader = ModelLoader(model)
        self._model_loader.finished.connect(self._on_model_loaded)
        self._model_loader.error.connect(self._on_model_error)
        self._model_loader.start()
    
    def _on_model_loaded(self, transcriber):
        self.transcriber = transcriber
        log("MODEL_LOADED", f"{transcriber.model_config.get('name', 'unknown')}")
    
    def _on_model_error(self, error):
        log("MODEL_LOAD_ERROR", error)
        self.transcriber = Transcriber()

    def show_settings(self):
        self.show()
        self.activateWindow()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_settings()

    def toggle_recording(self):
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def _start_drag(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_off = QCursor.pos() - self.pos()
            if not hasattr(self, "_drag_timer"):
                self._drag_timer = QTimer(self)
                self._drag_timer.timeout.connect(self._drag_tick)
            self._drag_timer.start(12)

    def _drag_tick(self):
        import ctypes
        if not (ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000):
            self._drag_timer.stop()
            return
        self.move(QCursor.pos() - self._drag_off)

    def hide_to_tray(self):
        self.hide()

    def closeEvent(self, event):
        event.ignore()
        self.hide_to_tray()

    def quit_app(self):
        self._stop_listener()
        self.tray.hide()
        QApplication.quit()

    def _open_help(self):
        help_path = os.path.join(get_base_dir(), "help.html")
        if os.path.exists(help_path):
            import webbrowser
            webbrowser.open("file:///" + help_path.replace("\\", "/"))
        else:
            QMessageBox.information(self, "Справка", "Файл справки не найден:\n" + help_path)

    def update_ad_banner(self):
        if self.ad_manager.show_banner():
            config = self.ad_manager.get_banner_config()
            img_path = self.ad_manager.get_banner_image_path()
            if img_path and os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                self.ad_banner.setPixmap(pixmap.scaled(380, 90, Qt.AspectRatioMode.KeepAspectRatio))
            else:
                self.ad_banner.setText("РЕКЛАМА")
                self.ad_banner.setStyleSheet("background-color: #16213e; border: 1px solid #00f7ff; border-radius: 5px; color: #00f7ff; font-size: 18px; font-weight: bold;")
        else:
            self.ad_banner.hide()

    def on_ad_banner_click(self, event):
        config = self.ad_manager.get_banner_config()
        link = config.get("link", "")
        if link:
            import webbrowser
            webbrowser.open(link)


def main():
    import traceback
    import ctypes
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("mihalanius.talkerbox")
    log_path = os.path.join(os.path.dirname(__file__), "crash.log")
    def excepthook(exc_type, exc_value, exc_tb):
        with open(log_path, "w", encoding="utf-8") as f:
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    sys.excepthook = excepthook

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    font = app.font()
    font.setFamily("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)
    window = MainWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
