import sys
import os
import time
import threading
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QLabel, QPushButton, QComboBox,
                              QCheckBox, QSystemTrayIcon, QMenu, QMessageBox,
                              QFileDialog, QLineEdit, QListWidget, QListWidgetItem,
                              QGroupBox, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPointF
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QBrush, QFont, QAction, QColor, QPen, QPolygonF
from recorder import Recorder
from transcriber import Transcriber
from settings_manager import SettingsManager
from ad_manager import AdManager
from waveform import WaveformWindow
from hotkey_hook import HotkeyListener, start_capture
from sounds import play_start_sound, play_stop_sound, play_hover_sound
from logger import log


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


class StarsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._stars = []
        self._init_stars(50)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(150)
        self._phase = 0

    def _init_stars(self, count):
        import random
        for _ in range(count):
            self._stars.append({
                'x': random.random(),
                'y': random.random(),
                'size': random.uniform(1, 2.5),
                'phase': random.random() * 6.28,
                'speed': random.uniform(0.02, 0.08),
            })

    def _tick(self):
        self._phase += 0.1
        self.update()

    def paintEvent(self, event):
        import math
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            w = self.width()
            h = self.height()
            for star in self._stars:
                opacity = 0.3 + 0.7 * abs(math.sin(self._phase * star['speed'] + star['phase']))
                color = QColor(255, 255, 255, int(opacity * 255))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(color))
                x = int(star['x'] * w)
                y = int(star['y'] * h)
                s = star['size']
                p.drawEllipse(x, y, int(s), int(s))
        finally:
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

    VK_CONTROL = 0x11
    VK_V = 0x56
    VK_RETURN = 0x0D
    VK_LSHIFT = 0xA0

    if is_terminal:
        send_key(VK_LSHIFT)
        send_key(VK_CONTROL)
        time.sleep(0.03)
        send_key(VK_V)
        time.sleep(0.03)
        send_key(VK_V, KEYEVENTF_KEYUP)
        send_key(VK_CONTROL, KEYEVENTF_KEYUP)
        send_key(VK_LSHIFT, KEYEVENTF_KEYUP)
    else:
        send_key(VK_CONTROL)
        time.sleep(0.03)
        send_key(VK_V)
        time.sleep(0.03)
        send_key(VK_V, KEYEVENTF_KEYUP)
        send_key(VK_CONTROL, KEYEVENTF_KEYUP)

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
        self.transcriber = None
        self.ad_manager = AdManager()
        self.signals = Signals()
        self.is_recording = False
        self.is_transcribing = False
        self.hold_mode = False
        self._suppress_hotkey = False
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
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "talkerbox.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setFixedSize(400, 350)
        self.setStyleSheet("""
            QMainWindow { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0a1628, stop:1 #1a1a2e); }
            QLabel { color: #eee; }
            QMessageBox {
                background-color: #1a1a2e;
            }
            QMessageBox QLabel {
                color: #00ff88;
            }
            QPushButton {
                background-color: #16213e;
                color: #00f7ff;
                border: 1px solid #00f7ff;
                border-radius: 5px;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #1a1a4e; }
            QComboBox, QLineEdit {
                background-color: #16213e;
                color: #eee;
                border: 1px solid #00f7ff;
                border-radius: 3px;
                padding: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #16213e;
                color: #ffffff;
                selection-background-color: #1a1a4e;
                selection-color: #ffffff;
                border: 1px solid #00f7ff;
            }
            QComboBox QAbstractItemView QScrollBar:vertical {
                background: #16213e;
                width: 10px;
                border-radius: 5px;
            }
            QComboBox QAbstractItemView QScrollBar::handle:vertical {
                background: #00ff88;
                min-height: 20px;
                border-radius: 5px;
            }
            QComboBox QAbstractItemView QScrollBar::add-line:vertical,
            QComboBox QAbstractItemView QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QCheckBox { color: #eee; }
            QListWidget {
                background-color: #16213e;
                color: #eee;
                border: none;
                padding: 0;
                margin: 0;
                outline: 0;
            }
            QListWidget::item {
                padding: 2px 4px;
                margin: 0;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(2)
        layout.setContentsMargins(10, 10, 10, 5)

        self._stars_widget = StarsWidget(central)
        self._stars_widget.lower()

        sep_line_top_hint = QWidget()
        sep_line_top_hint.setFixedHeight(3)
        sep_line_top_hint.setStyleSheet("background: transparent;")
        sep_line_top_hint.paintEvent = lambda e: self._paint_neon_line(sep_line_top_hint, e)
        layout.addWidget(sep_line_top_hint)

        spacer_top = QWidget()
        spacer_top.setFixedHeight(4)
        layout.addWidget(spacer_top)

        hint_label = QLabel("Откройте программу, где будете писать текст голосом.\nНаведите курсор на поле ввода текста, после чего:\nАктивируйте курсор в поле нажатием ЛКМ.\nНажмите горячую клавишу и начните говорить.")
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #00ff88; font-size: 11px; padding: 13px 12px; background-color: transparent; border: none;")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint_label)

        spacer = QWidget()
        spacer.setFixedHeight(6)
        layout.addWidget(spacer)

        sep_line = QWidget()
        sep_line.setFixedHeight(3)
        sep_line.setStyleSheet("background: transparent;")
        sep_line.paintEvent = lambda e: self._paint_neon_line(sep_line, e)
        layout.addWidget(sep_line)

        settings_group = NeonGroupBox("Настройки", show_corners=False)
        settings_layout = settings_group.layout()

        mode_layout = QHBoxLayout()
        mode_label = QLabel("Режим:")
        mode_label.setStyleSheet("font-size: 11px;")
        mode_layout.addWidget(mode_label)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Hold (удерживай)", "Toggle (нажал-нажал)"])
        self.mode_combo.setCurrentIndex(0 if self.settings.get("mode") == "hold" else 1)
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        self.mode_combo.setFixedHeight(18)
        self.mode_combo.setStyleSheet("""
            QComboBox {
                color: #00ff88;
                background: transparent;
                border: 1px solid #00ff88;
                border-radius: 2px;
                font: bold 11px 'Segoe UI';
                padding: 1px 6px;
            }
            QComboBox:hover {
                color: #000000;
                background: #00ff88;
            }
            QComboBox::drop-down {
                border: none;
                width: 14px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #00ff88;
                margin-right: 4px;
            }
            QComboBox QAbstractItemView {
                background-color: #1a1a2e;
                color: #00ff88;
                border: 1px solid #00ff88;
                selection-background-color: #00ff88;
                selection-color: #000;
            }
        """)
        mode_layout.addWidget(self.mode_combo)
        settings_layout.addLayout(mode_layout)

        auto_send_row = QHBoxLayout()
        auto_send_row.setContentsMargins(0, 0, 0, 0)
        auto_send_row.setSpacing(6)
        self.auto_send_toggle = NeonCheckBox(checked=self.settings.get("auto_send"))
        self.auto_send_toggle.toggled.connect(self.on_auto_send_toggled)
        auto_send_row.addWidget(self.auto_send_toggle)
        auto_send_label = QLabel("Авто-отправка (Enter)")
        auto_send_label.setStyleSheet("color: #eee; font-size: 11px;")
        auto_send_row.addWidget(auto_send_label)
        auto_send_row.addStretch()
        settings_layout.addLayout(auto_send_row)

        hotkey_layout = QHBoxLayout()
        hotkey_label = QLabel("Горячая клавиша:")
        hotkey_label.setStyleSheet("font-size: 11px;")
        hotkey_layout.addWidget(hotkey_label)
        self.hotkey_btn = QPushButton(self._format_hotkey(self.settings.get("hotkey", "f9")))
        self.hotkey_btn.setFixedHeight(18)
        self.hotkey_btn.setStyleSheet("""
            QPushButton {
                color: #00ff88;
                background: transparent;
                border: 1px solid #00ff88;
                border-radius: 2px;
                font: bold 11px 'Segoe UI';
                padding: 1px 6px;
            }
            QPushButton:hover {
                color: #000000;
                background: #00ff88;
            }
        """)
        self.hotkey_btn.clicked.connect(self.start_hotkey_capture)
        self._capturing_hotkey = False
        hotkey_layout.addWidget(self.hotkey_btn)
        settings_layout.addLayout(hotkey_layout)

        layout.addWidget(settings_group)

        model_group = NeonGroupBox("Модели", show_corners=False)
        model_layout = model_group.layout()
        model_layout.setContentsMargins(15, 0, 10, 0)

        model_row = QHBoxLayout()
        model_row.setContentsMargins(0, 0, 0, 0)
        model_row.setSpacing(6)

        self.model_name_label = QLabel()
        self.model_name_label.setStyleSheet("color: #eee; font-size: 11px; padding: 2px 0;")
        self.model_name_label.setWordWrap(True)
        model_row.addWidget(self.model_name_label, 1)

        change_btn_style = """
            QPushButton {
                color: #00ff88;
                background: transparent;
                border: 1px solid #00ff88;
                border-radius: 2px;
                font: bold 11px 'Segoe UI';
                padding: 1px 6px;
            }
            QPushButton:hover {
                color: #000000;
                background: #00ff88;
            }
        """
        self.change_model_btn = QPushButton("Сменить Модель")
        self.change_model_btn.setStyleSheet(change_btn_style)
        self.change_model_btn.setFixedHeight(18)
        self.change_model_btn.setFixedWidth(160)
        self.change_model_btn.clicked.connect(self._load_new_model)
        model_row.addWidget(self.change_model_btn)

        model_layout.addLayout(model_row)
        self._update_model_label()

        layout.addWidget(model_group)

        self.neon_active_top = QWidget()
        self.neon_active_top.setFixedHeight(2)
        self.neon_active_top.setStyleSheet("background: transparent;")
        self.neon_active_top._color = "#333"
        self.neon_active_top.paintEvent = lambda e: self._paint_neon_active(self.neon_active_top, e)
        layout.addWidget(self.neon_active_top)

        sep_line_top = QWidget()
        sep_line_top.setFixedHeight(2)
        sep_line_top.setStyleSheet("background: transparent;")
        sep_line_top.paintEvent = lambda e: self._paint_neon_line(sep_line_top, e)
        layout.addWidget(sep_line_top)

        version_layout = QHBoxLayout()
        version_layout.setContentsMargins(0, 0, 0, 0)
        version_layout.setSpacing(20)
        version_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        help_btn = QPushButton("Справка")
        help_btn.setStyleSheet("""
            QPushButton {
                color: #00f7ff;
                background: transparent;
                border: none;
                font: 11px 'Segoe UI';
                padding: 0px;
            }
            QPushButton:hover {
                color: #00ff88;
                text-decoration: underline;
            }
        """)
        help_btn.clicked.connect(self._open_help)
        version_layout.addWidget(help_btn)

        version_label = QLabel("Talker Box v.1.16 © Glab 2026")
        version_label.setFixedHeight(14)
        version_label.setStyleSheet("color: #00ff88; font-size: 11px; padding: 0px; margin: 0px;")
        version_layout.addWidget(version_label)

        neon_line = QWidget()
        neon_line.setFixedHeight(3)
        neon_line.setStyleSheet("background: transparent;")
        neon_line.paintEvent = lambda e: self._paint_neon_line(neon_line, e)

        self.neon_active = QWidget()
        self.neon_active.setFixedHeight(3)
        self.neon_active.setStyleSheet("background: transparent;")
        self.neon_active._color = "#333"
        self.neon_active.paintEvent = lambda e: self._paint_neon_active(self.neon_active, e)

        bottom_group = QVBoxLayout()
        bottom_group.setContentsMargins(0, 0, 0, 0)
        bottom_group.setSpacing(0)
        bottom_group.addLayout(version_layout)
        bottom_group.addWidget(neon_line)
        bottom_group.addWidget(self.neon_active)
        layout.addLayout(bottom_group)

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
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "talkerbox.png")
        if os.path.exists(icon_path):
            self.tray.setIcon(QIcon(icon_path))
        else:
            self.tray.setIcon(self.create_mic_icon("#00f7ff"))

        tray_menu = QMenu()

        settings_action = QAction("Настройки", self)
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addAction(settings_action)

        models_action = QAction("Модели", self)
        models_action.triggered.connect(self.show_models)
        tray_menu.addAction(models_action)

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
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(16, 8, 32, 40)
        painter.drawEllipse(22, 36, 20, 10)
        painter.drawRect(28, 46, 8, 12)
        painter.drawRect(18, 44, 28, 4)
        painter.end()
        return QIcon(pixmap)

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
            )
            self._hotkey_listener.start()
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
                else:
                    self.start_recording()
            else:
                if not self.is_recording:
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
            self._recording_start_time = time.monotonic()
            self.recorder.start()
            self.signals.recording_started.emit()
            self.waveform.show_recording()
            play_start_sound()
            self._recording_session = getattr(self, '_recording_session', 0) + 1
            session = self._recording_session
            self._recording_timeout = QTimer.singleShot(60000, lambda s=session: self._on_recording_timeout(s))

    def _on_recording_timeout(self, session):
        if session == getattr(self, '_recording_session', 0):
            self._force_stop_recording()

    def _force_stop_recording(self):
        if self.is_recording:
            elapsed = time.monotonic() - getattr(self, '_recording_start_time', 0)
            log("RECORD_TIMEOUT", f"60s limit reached (elapsed={elapsed:.1f}s)")
            self._recording_timeout = None
            self.stop_recording()

    def stop_recording(self):
        if self.is_recording:
            if hasattr(self, '_recording_timeout') and self._recording_timeout:
                self._recording_timeout.stop()
                self._recording_timeout = None
            audio = self.recorder.stop()
            frames = len(audio) if len(audio) > 0 else 0
            duration = frames / 16000 if frames > 0 else 0
            log("RECORD_STOP", f"frames={frames} duration={duration:.1f}s")
            self.is_recording = False
            self.signals.recording_stopped.emit()
            self.waveform.hide_wave()
            play_stop_sound()
            self.signals.transcribing_started.emit()
            threading.Thread(target=self.transcribe_audio, args=(audio,), daemon=True).start()

    def transcribe_audio(self, audio):
        elapsed = time.monotonic() - getattr(self, '_recording_start_time', time.monotonic())
        if elapsed > 65:
            log("TRANSCRIBE_SKIP", f"stale audio from {elapsed:.1f}s ago")
            self.signals.transcribing_finished.emit()
            return
        if self.transcriber and len(audio) > 0:
            try:
                log("TRANSCRIBE_START", f"frames={len(audio)} elapsed={elapsed:.1f}s")
                text = self.transcriber.transcribe(audio)
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
        self._suppress_hotkey = True
        try:
            import pyperclip
            pyperclip.copy(text)
            log("CLIPBOARD_SET", "ok")
            QTimer.singleShot(100, lambda: self._do_paste(text))
        except Exception as e:
            log("PASTE_ERROR", str(e))
            self._suppress_hotkey = False

    def _do_paste(self, text):
        try:
            log("DO_PASTE", f"auto_send={self.settings.get('auto_send')}")
            is_terminal = _is_terminal()
            _paste_via_sendinput(text, auto_send=self.settings.get("auto_send"), is_terminal=is_terminal)
            log("DO_PASTE_DONE", "ok")
        except Exception as e:
            log("PASTE_ERROR", str(e))
        finally:
            QTimer.singleShot(300, self._release_hotkey_suppress)

    def _release_hotkey_suppress(self):
        self._suppress_hotkey = False

    def on_recording_started(self):
        self.neon_active._color = "#00ff88"
        self.neon_active.update()
        self.neon_active_top._color = "#00ff88"
        self.neon_active_top.update()
        self.tray.setIcon(self.create_mic_icon("#00ff88"))

    def on_recording_stopped(self):
        self.neon_active._color = "#f7ff00"
        self.neon_active.update()
        self.neon_active_top._color = "#f7ff00"
        self.neon_active_top.update()
        self.tray.setIcon(self.create_mic_icon("#f7ff00"))

    def on_transcribing_started(self):
        self.is_transcribing = True
        self.neon_active._color = "#00f7ff"
        self.neon_active.update()
        self.neon_active_top._color = "#00f7ff"
        self.neon_active_top.update()
        self.waveform.show_transcribing()

    def on_transcribing_finished(self):
        self.is_transcribing = False
        self.neon_active._color = "#333"
        self.neon_active.update()
        self.neon_active_top._color = "#333"
        self.neon_active_top.update()
        self.waveform.hide_wave()
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "talkerbox.png")
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

    def _format_hotkey(self, hotkey):
        modifier_order = {"ctrl": 0, "shift": 1, "alt": 2, "win": 3}
        parts = hotkey.split("+")
        parts.sort(key=lambda p: modifier_order.get(p.lower(), 99))
        return "+".join(p.capitalize() for p in parts)

    def start_hotkey_capture(self):
        self._stop_listener()
        self._capturing_hotkey = True
        self.hotkey_btn.setText("Нажмите клавишу (или комбинацию)...")
        self.hotkey_btn.setStyleSheet("""
            QPushButton {
                color: #000;
                background: #00ff88;
                border: 1px solid #00ff88;
                border-radius: 2px;
                font: bold 11px 'Segoe UI';
                padding: 1px 6px;
            }
        """)
        start_capture(self._on_hotkey_captured)

    def _on_hotkey_captured(self, combo):
        self._capturing_hotkey = False
        default_style = """
            QPushButton {
                color: #00ff88;
                background: transparent;
                border: 1px solid #00ff88;
                border-radius: 2px;
                font: bold 11px 'Segoe UI';
                padding: 1px 6px;
            }
            QPushButton:hover {
                color: #000000;
                background: #00ff88;
            }
        """
        if combo:
            self.settings.set("hotkey", combo)
            self.hotkey_btn.setText(self._format_hotkey(combo))
            self.hotkey_btn.setStyleSheet(default_style)
            QTimer.singleShot(100, lambda c=combo: self._start_listener(c))
        else:
            hotkey = self.settings.get("hotkey", "ctrl+win")
            self.hotkey_btn.setText(self._format_hotkey(hotkey))
            self.hotkey_btn.setStyleSheet(default_style)
            QTimer.singleShot(100, lambda h=hotkey: self._start_listener(h))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_stars_widget'):
            self._stars_widget.resize(self.centralWidget().size())

    def eventFilter(self, obj, event):
        return super().eventFilter(obj, event) if hasattr(super(), 'eventFilter') else False

    def keyPressEvent(self, event):
        return super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        return super().keyReleaseEvent(event)

    def _update_model_label(self):
        active = self.settings.get("active_model", "")
        if active:
            models = self.settings.get("models", [])
            size = ""
            for m in models:
                if m["name"] == active:
                    size = f" ({m['size']})" if m.get("size") else ""
                    break
            self.model_name_label.setText(f"● {active}{size}")
            self.model_name_label.setStyleSheet("color: #00ff88; font-size: 11px; padding: 2px 0;")
        else:
            self.model_name_label.setText("Модель не загружена")
            self.model_name_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px 0;")

    def _detect_model_type(self, path):
        if not os.path.isdir(path):
            return "unknown"
        files = os.listdir(path)
        names_lower = [f.lower() for f in files]
        all_lower = " ".join(names_lower)
        has_onnx = any(f.endswith(".onnx") for f in names_lower)
        has_tokens = any("tokens" in f for f in names_lower)
        has_encoder = any("encoder" in f for f in names_lower)
        has_decoder = any("decoder" in f for f in names_lower)
        has_joint = any("joint" in f or "joiner" in f for f in names_lower)
        has_final_mdl = any("final.mdl" in f for f in names_lower)
        has_am = any(f == "am" for f in names_lower)
        has_conf = any(f == "conf" for f in names_lower)
        has_graph = any(f == "graph" for f in names_lower)
        has_whisper_pattern = any(("-encoder.onnx" in f or "-decoder.onnx" in f) for f in names_lower)
        if has_whisper_pattern and has_tokens:
            return "whisper"
        if "whisper" in all_lower and has_onnx:
            return "whisper"
        if has_encoder and has_decoder and has_tokens and has_joint:
            return "sherpa-onnx"
        if has_encoder and has_decoder and has_tokens:
            return "sherpa-onnx"
        if has_onnx and has_tokens:
            return "sherpa-onnx"
        if has_final_mdl or (has_am and has_conf and has_graph):
            return "vosk"
        return "unknown"

    def _load_new_model(self):
        path = QFileDialog.getExistingDirectory(self, "Выберите папку с моделью")
        if not path:
            return
        name = os.path.basename(path)
        model_type = self._detect_model_type(path)

        if model_type == "unknown":
            QMessageBox.warning(self, "Модель", f"Не удалось определить тип модели в папке:\n{name}\n\nПоддерживаются: sherpa-onnx, vosk, whisper")
            return

        model = {
            "name": name,
            "path": path,
            "type": model_type,
            "language": "ru",
            "size": ""
        }

        try:
            test = Transcriber(model)
        except Exception as e:
            QMessageBox.warning(self, "Модель", f"Модель не загрузилась:\n{name}\n\nОшибка: {e}")
            return

        if not test.recognizer:
            QMessageBox.warning(self, "Модель", f"Модель не загрузилась:\n{name}\n\nТип: {model_type}\nПроверьте что файлы модели на месте.")
            return

        self.settings.set("models", [model])
        self.settings.set("active_model", name)
        self.transcriber = test
        self._update_model_label()

    def load_active_model(self):
        active_name = self.settings.get("active_model")
        models = self.settings.get("models", [])
        for model in models:
            if model["name"] == active_name:
                try:
                    self.transcriber = Transcriber(model)
                except Exception as e:
                    log("MODEL_LOAD_CRASH", f"{active_name}: {e}")
                    self.transcriber = Transcriber()
                if not self.transcriber.recognizer:
                    log("MODEL_LOAD_FAIL", f"{active_name} (type={model.get('type')})")
                break
        self._update_model_label()

    def show_settings(self):
        self.show()
        self.activateWindow()

    def show_models(self):
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
        help_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "help.html")
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
