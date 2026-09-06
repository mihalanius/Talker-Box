import sys
import os
import time
import threading
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QLabel, QPushButton, QComboBox,
                              QCheckBox, QSystemTrayIcon, QMenu, QMessageBox,
                              QLineEdit, QListWidget, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPointF
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QBrush, QFont, QAction, QColor, QPen, QPolygonF, QFontDatabase, QFontMetrics
from recorder import Recorder
from transcriber import Transcriber
from settings_manager import SettingsManager
from ad_manager import AdManager
from waveform import WaveformWindow
from hotkey_hook import HotkeyListener, start_capture
from sounds import play_start_sound, play_stop_sound, play_hover_sound
from logger import log

def _get_base_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(__file__))

def _get_exe_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(__file__))


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
        icon_path = os.path.join(_get_base_dir(), "talkerbox.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setFixedSize(585, 419)
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0d1225, stop:0.5 #111830, stop:1 #0a0f1f);
            }
            QLabel { color: #e0e0e0; background: transparent; }
            QMessageBox { background-color: #1a1a2e; }
            QMessageBox QLabel { color: #00ff88; }
            QPushButton {
                background-color: transparent;
                color: #aaa;
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 18px;
                padding: 0;
                font-size: 14px;
            }
            QPushButton:hover {
                border-color: #00ff88;
                color: #00ff88;
            }
        """)

        central = QWidget()
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(0)

        header = QHBoxLayout()
        header.setSpacing(6)
        header_left = QHBoxLayout()
        header_left.setSpacing(8)
        logo_label = QLabel()
        logo_label.setFixedSize(32, 32)
        logo_label.setStyleSheet("background: transparent;")
        logo_label.paintEvent = lambda e: self._paint_cube_logo(logo_label, e)
        header_left.addWidget(logo_label)
        title = NeonLabel("Talker Box", font_size=17, color="#00ff88")
        font_path = os.path.join(_get_base_dir(), "fonts", "Orbitron.ttf")
        if os.path.exists(font_path):
            QFontDatabase.addApplicationFont(font_path)
            title._font_family = "Orbitron"
        header_left.addWidget(title)
        header.addLayout(header_left)
        header.addStretch()

        self.btn_help = QPushButton("?")
        self.btn_help.setFixedSize(36, 36)
        self.btn_help.setStyleSheet("QPushButton { background: transparent; border: none; }")
        self.btn_help.clicked.connect(self._open_help)
        self.btn_help.paintEvent = lambda e: self._paint_header_btn(self.btn_help, e, "help")
        header.addWidget(self.btn_help)

        btn_tray = QPushButton()
        btn_tray.setFixedSize(36, 36)
        btn_tray.setStyleSheet("QPushButton { background: transparent; border: none; }")
        btn_tray.clicked.connect(self.hide_to_tray)
        btn_tray.paintEvent = lambda e: self._paint_header_btn(btn_tray, e, "minimize")
        header.addWidget(btn_tray)

        btn_close = QPushButton()
        btn_close.setFixedSize(36, 36)
        btn_close.setStyleSheet("QPushButton { background: transparent; border: none; }")
        btn_close.clicked.connect(self.quit_app)
        btn_close.paintEvent = lambda e: self._paint_header_btn(btn_close, e, "close")
        header.addWidget(btn_close)
        root.addLayout(header)

        spacer1 = QWidget()
        spacer1.setFixedHeight(6)
        root.addWidget(spacer1)

        hint_widget = QWidget()
        hint_widget.setStyleSheet("""
            QWidget {
                background: rgba(0,255,136,0.04);
                border: 1px solid rgba(0,255,136,0.1);
                border-radius: 10px;
            }
        """)
        hint_layout = QHBoxLayout(hint_widget)
        hint_layout.setContentsMargins(12, 6, 12, 6)
        hint_label = QLabel(
            "Откройте программу, где будете писать текст голосом. Наведите курсор на «поле ввода текста», "
            "после чего активизируйте курсор в «поле ввода текста» нажатием клавиши «ЛКМ». "
            "Нажмите горячую клавишу и начните начитывать текст в Word или общаться с агентами AI."
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #00ff88; font-size: 11px; background: transparent; border: none;")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignJustify)
        hint_layout.addWidget(hint_label)
        root.addWidget(hint_widget)

        spacer2 = QWidget()
        spacer2.setFixedHeight(8)
        root.addWidget(spacer2)

        main_row = QHBoxLayout()
        main_row.setSpacing(12)

        self.hold_panel = self._create_mode_panel("Режим Hold", "Удерживать",
            "Нажмите и удерживайте горячую клавишу пока диктуете текст и микрофон активен.", True)
        main_row.addWidget(self.hold_panel)

        center_widget = self._create_center_widget()
        main_row.addWidget(center_widget, 1)

        self.toggle_panel = self._create_mode_panel("Режим Toggle", "Нажал \u2014 нажал",
            "Нажмите Хоткей, чтобы начать запись и снова нажмите чтобы остановить запись.", False)
        main_row.addWidget(self.toggle_panel)
        root.addLayout(main_row)

        spacer3 = QWidget()
        spacer3.setFixedHeight(10)
        root.addWidget(spacer3)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        auto_widget = QWidget()
        auto_widget.setFixedHeight(60)
        auto_widget.setStyleSheet("""
            QWidget {
                background: rgba(0,255,136,0.03);
                border: 1px solid rgba(0,255,136,0.12);
                border-radius: 14px;
            }
        """)
        auto_layout = QVBoxLayout(auto_widget)
        auto_layout.setContentsMargins(14, 10, 14, 10)
        auto_layout.setSpacing(2)
        auto_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        auto_header = QHBoxLayout()
        auto_title = QLabel("Авто-отправка (Enter)")
        auto_title.setStyleSheet("color: #00ff88; font: bold 12px 'Segoe UI'; background: transparent; border: none;")
        auto_header.addWidget(auto_title)
        auto_header.addStretch()
        self.auto_send_toggle = NeonCheckBox(checked=self.settings.get("auto_send"))
        self.auto_send_toggle.toggled.connect(self.on_auto_send_toggled)
        auto_header.addWidget(self.auto_send_toggle)
        auto_layout.addLayout(auto_header)
        auto_desc = QLabel("Отправляет текст после окончания записи")
        auto_desc.setStyleSheet("color: #666; font-size: 11px; background: transparent; border: none;")
        auto_layout.addWidget(auto_desc)
        bottom_row.addWidget(auto_widget)

        hotkey_widget = QWidget()
        hotkey_widget.setFixedHeight(60)
        hotkey_widget.setStyleSheet("""
            QWidget {
                background: rgba(0,255,136,0.03);
                border: 1px solid rgba(0,255,136,0.12);
                border-radius: 14px;
            }
        """)
        hotkey_layout = QVBoxLayout(hotkey_widget)
        hotkey_layout.setContentsMargins(14, 10, 14, 10)
        hotkey_layout.setSpacing(2)
        hotkey_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        hotkey_header = QHBoxLayout()
        hotkey_title = QLabel("Горячая клавиша")
        hotkey_title.setStyleSheet("color: #00ff88; font: bold 12px 'Segoe UI'; background: transparent; border: none;")
        hotkey_header.addWidget(hotkey_title)
        hotkey_header.addStretch()
        self.hotkey_btn = QPushButton(self._format_hotkey(self.settings.get("hotkey", "f9")))
        self.hotkey_btn.setFixedHeight(18)
        self.hotkey_btn.setStyleSheet("""
            QPushButton {
                color: #00ff88; background: transparent;
                border: 1px solid rgba(0,255,136,0.3); border-radius: 4px;
                font: bold 12px 'Segoe UI'; padding: 0px 8px;
            }
            QPushButton:hover {
                border-color: #00ff88;
                background: rgba(0,255,136,0.08);
            }
        """)
        self.hotkey_btn.clicked.connect(self.start_hotkey_capture)
        self._capturing_hotkey = False
        hotkey_header.addWidget(self.hotkey_btn)
        hotkey_layout.addLayout(hotkey_header)
        hotkey_desc = QLabel("Нажмите любую клавишу или комбинацию")
        hotkey_desc.setStyleSheet("color: #666; font-size: 11px; background: transparent; border: none;")
        hotkey_layout.addWidget(hotkey_desc)
        bottom_row.addWidget(hotkey_widget)
        root.addLayout(bottom_row)

    def _paint_cube_logo(self, widget, event):
        p = QPainter(widget)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#00ff88"), 1.5))
        p.setBrush(QBrush(QColor(0, 255, 136, 30)))
        p.drawPolygon(QPolygonF([QPointF(16, 2), QPointF(30, 9), QPointF(16, 16), QPointF(2, 9)]))
        p.setBrush(QBrush(QColor(0, 255, 136, 15)))
        p.drawPolygon(QPolygonF([QPointF(2, 9), QPointF(16, 16), QPointF(16, 30), QPointF(2, 23)]))
        p.setBrush(QBrush(QColor(0, 255, 136, 20)))
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
        panel = QWidget()
        panel.setCursor(Qt.CursorShape.PointingHandCursor)
        panel._active = active
        self._update_panel_style(panel, active)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 28, 10, 12)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        icon_container = QWidget()
        icon_container.setFixedSize(44, 44)
        icon_container._is_hold = "HOLD" in subtitle.upper()
        icon_container.setStyleSheet(f"""
            border: 2px solid {'#00ff88' if active else '#444'};
            border-radius: 22px;
            background: {'rgba(0,255,136,0.1)' if active else 'transparent'};
        """)
        icon_container.paintEvent = lambda e, ic=icon_container, at=active: self._paint_mode_icon(ic, e, at)
        icon_container._is_hold = "HOLD" in subtitle.upper()
        panel._icon_container = icon_container
        layout.addWidget(icon_container, alignment=Qt.AlignmentFlag.AlignHCenter)

        sub = QLabel(subtitle.upper())
        sub.setStyleSheet(f"color: {'#00ff88' if active else '#666'}; font: bold 12px 'Segoe UI'; background: transparent; border: none; text-transform: uppercase;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        t = QLabel(title)
        t.setStyleSheet(f"color: {'#00ff88' if active else '#666'}; font: bold 14px 'Segoe UI'; background: transparent; border: none;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(t)

        d = QLabel(desc)
        d.setWordWrap(True)
        d.setStyleSheet("color: #888; font-size: 11px; background: transparent; border: none;")
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(d)

        panel.mousePressEvent = lambda e, p=panel, s=subtitle: self._on_panel_click(p, s)
        panel._title_label = t
        panel._subtitle_label = sub
        return panel

    def _update_panel_style(self, panel, active):
        panel.setStyleSheet(f"""
            QWidget {{
                background: rgba(0,255,136,0.03);
                border: 2px solid {'#00ff88' if active else '#444'};
                border-radius: 16px;
            }}
            QWidget:hover {{
                border-color: {'#00ff88' if active else '#666'};
            }}
        """)

    def _paint_mode_icon(self, widget, event, active):
        p = QPainter(widget)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = "#00ff88" if active else "#555"
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
            wav = os.path.join(_get_base_dir(), "sounds", "ping.wav")
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
        color = "#00ff88" if active else "#666"
        panel._subtitle_label.setStyleSheet(f"color: {color}; font: bold 12px 'Segoe UI'; background: transparent; border: none;")
        panel._title_label.setStyleSheet(f"color: {color}; font: bold 14px 'Segoe UI'; background: transparent; border: none;")
        icon_container = panel._icon_container
        icon_container.setStyleSheet(f"""
            border: 2px solid {'#00ff88' if active else '#444'};
            border-radius: 22px;
            background: {'rgba(0,255,136,0.1)' if active else 'transparent'};
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
        mascot_path = os.path.join(_get_base_dir(), "mascot.png")
        if os.path.exists(mascot_path):
            self._mascot_label.setPixmap(QPixmap(mascot_path).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self._mascot_label.setText("\U0001f916")
            self._mascot_label.setStyleSheet("font-size: 48px; background: transparent; border: none;")
        self._mascot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mascot_label.setParent(self._circle_widget)
        self._mascot_label.setFixedSize(80, 80)
        self._mascot_label.move(60, 35)

        sig_label = QLabel("УРОВЕНЬ СИГНАЛА")
        sig_label.setStyleSheet("color: #666; font-size: 8px; font-weight: bold; letter-spacing: 2px; background: transparent; border: none;")
        sig_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sig_label.setParent(self._circle_widget)
        sig_label.setFixedSize(180, 14)
        sig_label.move(10, 120)

        self._signal_value_label = QLabel(f"{self._signal_level}%")
        self._signal_value_label.setStyleSheet("color: #00ff88; font: bold 28px 'Segoe UI'; background: transparent; border: none;")
        self._signal_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._signal_value_label.setParent(self._circle_widget)
        self._signal_value_label.setFixedSize(180, 36)
        self._signal_value_label.move(10, 132)

        self._signal_timer = QTimer()
        self._signal_timer.timeout.connect(self._update_signal)
        self._signal_timer.start(1500)

        return widget

    def _paint_circle(self, widget, event):
        p = QPainter(widget)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = widget.width(), widget.height()
        cx, cy, r = w // 2, h // 2, 90

        pen_track = QPen(QColor(0, 255, 136, 20), 4)
        p.setPen(pen_track)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        span = int(360 * 16 * self._signal_level / 100)
        pen_active = QPen(QColor("#00ff88"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen_active)
        p.drawArc(cx - r, cy - r, r * 2, r * 2, 90 * 16, -span)

        r2 = r - 4 - 3
        if self.is_recording:
            pen_inner = QPen(QColor("#00ff88"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen_inner)
            p.drawEllipse(cx - r2, cy - r2, r2 * 2, r2 * 2)
            glow = QColor(0, 255, 136, 30)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(glow))
            p.drawEllipse(cx - r2 - 4, cy - r2 - 4, r2 * 2 + 8, r2 * 2 + 8)
        else:
            pen_inner = QPen(QColor(0, 255, 136, 30), 2)
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
        icon_path = os.path.join(_get_base_dir(), "talkerbox.png")
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
        p.setBrush(QBrush(QColor(color).darker(300)))
        p.drawEllipse(4, 4, 56, 56)
        icon_path = os.path.join(_get_base_dir(), "talkerbox.png")
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
        self._circle_widget.update()
        self.tray.setIcon(self.create_mic_icon("#00ff88"))

    def on_recording_stopped(self):
        self._circle_widget.update()
        self.tray.setIcon(self.create_mic_icon("#f7ff00"))

    def on_transcribing_started(self):
        self.is_transcribing = True
        self.tray.setIcon(self.create_mic_icon("#00f7ff"))
        self.waveform.show_transcribing()

    def on_transcribing_finished(self):
        self.is_transcribing = False
        self.waveform.hide_wave()
        icon_path = os.path.join(_get_base_dir(), "talkerbox.png")
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
            wav = os.path.join(_get_base_dir(), "sounds", sound)
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
                font: bold 12px 'Segoe UI';
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
            try:
                import winsound
                wav = os.path.join(_get_base_dir(), "sounds", "transition_up.wav")
                if os.path.exists(wav):
                    winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except:
                pass
            QTimer.singleShot(100, lambda c=combo: self._start_listener(c))
        else:
            hotkey = self.settings.get("hotkey", "ctrl+win")
            self.hotkey_btn.setText(self._format_hotkey(hotkey))
            self.hotkey_btn.setStyleSheet(default_style)
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
        model_path = os.path.join(_get_exe_dir(), BUILTIN_MODEL["path"])
        model = dict(BUILTIN_MODEL, path=model_path)
        try:
            self.transcriber = Transcriber(model)
        except Exception as e:
            log("MODEL_LOAD_CRASH", f"{model['name']}: {e}")
            self.transcriber = Transcriber()
        if not self.transcriber.recognizer:
            log("MODEL_LOAD_FAIL", f"{model['name']} (type={model.get('type')})")

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
        help_path = os.path.join(_get_base_dir(), "help.html")
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
