import sys
import os
import time
import threading
import subprocess
import queue
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QLabel, QPushButton, QComboBox,
                              QCheckBox, QSystemTrayIcon, QMenu, QMessageBox,
                              QFileDialog, QLineEdit, QListWidget, QListWidgetItem,
                              QGroupBox, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QBrush, QFont, QAction, QColor, QPen
from recorder import Recorder
from transcriber import Transcriber
from settings_manager import SettingsManager
from ad_manager import AdManager
from waveform import WaveformWindow
from sounds import play_start_sound, play_stop_sound
from logger import log


class NeonFrame(QFrame):
    def __init__(self, parent=None, color="#00ff88", corner_size=12, thickness=2):
        super().__init__(parent)
        self._color = QColor(color)
        self._corner_size = corner_size
        self._thickness = thickness
        self.setStyleSheet("background: transparent; border: none;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._color, self._thickness)
        painter.setPen(pen)
        w, h, s = self.width(), self.height(), self._corner_size
        painter.drawLine(0, s, 0, 0)
        painter.drawLine(0, 0, s, 0)
        painter.drawLine(w - s, 0, w, 0)
        painter.drawLine(w, 0, w, s)
        painter.drawLine(0, h - s, 0, h)
        painter.drawLine(0, h, s, h)
        painter.drawLine(w - s, h, w, h)
        painter.drawLine(w, h - s, w, h)
        painter.end()


class NeonGroupBox(QWidget):
    def __init__(self, title="", parent=None, color="#00ff88", corner_size=12, thickness=2):
        super().__init__(parent)
        self._title = title
        self._color = QColor(color)
        self._corner_size = corner_size
        self._thickness = thickness
        self.setStyleSheet("background: transparent;")

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        if title:
            self._title_label = QLabel(title)
            self._title_label.setStyleSheet(f"color: {color}; background: transparent; font: bold 12px 'Segoe UI';")
            self._title_label.setContentsMargins(15, 0, 0, 0)
            self._title_label.setFixedHeight(16)
            self._outer.addWidget(self._title_label)

        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(15, 2, 10, 10)
        self._outer.addWidget(self._inner)

    def layout(self):
        return self._layout

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h, s = self.width(), self.height(), self._corner_size
        pen = QPen(self._color, self._thickness)
        painter.setPen(pen)
        painter.drawLine(0, s, 0, 0)
        painter.drawLine(0, 0, s, 0)
        painter.drawLine(w - s, 0, w, 0)
        painter.drawLine(w, 0, w, s)
        painter.drawLine(0, h - s, 0, h)
        painter.drawLine(0, h, s, h)
        painter.drawLine(w - s, h, w, h)
        painter.drawLine(w, h - s, w, h)
        if self._title:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            dash_pen = QPen(self._color, 1, Qt.PenStyle.DashLine)
            painter.setPen(dash_pen)
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(self._title) + 20
            painter.drawLine(text_w, 8, w - s - 4, 8)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.end()


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
        self._listener_proc = None
        self._listener_reader = None
        self._listener_alive = False
        self._last_heartbeat = 0

        self.signals.text_ready.connect(self.on_text_ready)
        self.signals.recording_started.connect(self.on_recording_started)
        self.signals.recording_stopped.connect(self.on_recording_stopped)
        self.signals.transcribing_started.connect(self.on_transcribing_started)
        self.signals.transcribing_finished.connect(self.on_transcribing_finished)

        self.init_ui()
        self.init_tray()
        self.init_hotkey()
        self.load_active_model()
        self.init_ad_timer()
        self.init_waveform()
        self.init_watchdog()
        self.show()

        if self.settings.get("minimize_to_tray") and "--minimized" in sys.argv:
            QTimer.singleShot(100, self.hide_to_tray)

    def init_ui(self):
        self.setWindowTitle("Talker Box")
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "talkerbox.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setFixedSize(400, 450)
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a2e; }
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
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        hint_label = QLabel("Сверните Talker Box в трей → Откройте программу, наведите курсор на поле ввода текста → Нажмите горячую клавишу и начните говорить.")
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #00ff88; font-size: 11px; padding: 8px 12px; background-color: #1a1b26; border: 1px solid #00ff88; border-radius: 5px;")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint_label)

        settings_group = NeonGroupBox("Настройки")
        settings_layout = settings_group.layout()

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Режим:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Hold (удерживай)", "Toggle (нажал-нажал)"])
        self.mode_combo.setCurrentIndex(0 if self.settings.get("mode") == "hold" else 1)
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        settings_layout.addLayout(mode_layout)

        self.auto_send_cb = QCheckBox("Авто-отправка (Enter)")
        self.auto_send_cb.setChecked(self.settings.get("auto_send"))
        self.auto_send_cb.stateChanged.connect(self.on_auto_send_changed)
        self.auto_send_cb.setStyleSheet("""
            QCheckBox::indicator {
                width: 40px;
                height: 20px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #333;
                border: 1px solid #00f7ff;
                border-radius: 10px;
            }
            QCheckBox::indicator:checked {
                background-color: #00ff88;
                border: 1px solid #00ff88;
                border-radius: 10px;
            }
        """)
        settings_layout.addWidget(self.auto_send_cb)

        hotkey_layout = QHBoxLayout()
        hotkey_layout.addWidget(QLabel("Горячая клавиша:"))
        self.hotkey_btn = QPushButton(self.settings.get("hotkey", "f9").upper())
        self.hotkey_btn.setFixedHeight(30)
        self.hotkey_btn.clicked.connect(self.start_hotkey_capture)
        self._capturing_hotkey = False
        hotkey_layout.addWidget(self.hotkey_btn)
        settings_layout.addLayout(hotkey_layout)

        layout.addWidget(settings_group)

        model_group = NeonGroupBox("Модели")
        model_layout = model_group.layout()

        model_list_frame = NeonFrame(corner_size=6, thickness=2)
        model_list_frame_layout = QVBoxLayout(model_list_frame)
        model_list_frame_layout.setContentsMargins(4, 4, 4, 4)

        self.model_list = QListWidget()
        self.model_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.model_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.update_model_list()
        model_list_frame_layout.addWidget(self.model_list)
        model_layout.addWidget(model_list_frame)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_style = """
            QPushButton {
                color: #00ff88;
                background: transparent;
                border: 1px solid #00ff88;
                border-radius: 2px;
                font: bold 11px 'Segoe UI';
                padding: 2px 8px;
            }
            QPushButton:hover {
                color: #000000;
                background: #00ff88;
            }
        """

        self.add_model_btn = QPushButton("+ Добавить")
        self.add_model_btn.setStyleSheet(btn_style)
        self.add_model_btn.setFixedHeight(22)
        self.add_model_btn.clicked.connect(self.add_model)
        btn_layout.addWidget(self.add_model_btn)

        self.remove_model_btn = QPushButton("- Удалить")
        self.remove_model_btn.setStyleSheet(btn_style)
        self.remove_model_btn.setFixedHeight(22)
        self.remove_model_btn.clicked.connect(self.remove_model)
        btn_layout.addWidget(self.remove_model_btn)

        self.set_active_btn = QPushButton("Выбрать")
        self.set_active_btn.setStyleSheet(btn_style)
        self.set_active_btn.setFixedHeight(22)
        self.set_active_btn.clicked.connect(self.set_active_model)
        btn_layout.addWidget(self.set_active_btn)

        model_layout.addLayout(btn_layout)
        layout.addWidget(model_group)

        self.mic_indicator = TaperedBar(color="#333", height=5)
        layout.addWidget(self.mic_indicator)

        self.ad_banner = QLabel()
        self.ad_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ad_banner.setFixedHeight(100)
        self.ad_banner.setStyleSheet("background-color: #16213e; border: 1px solid #333; border-radius: 5px;")
        self.ad_banner.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ad_banner.mousePressEvent = self.on_ad_banner_click
        layout.addWidget(self.ad_banner)
        self.update_ad_banner()

        version_label = QLabel("Версия 1.14")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #00ff88; font-size: 11px; padding: 5px;")
        layout.addWidget(version_label)

    def init_ad_timer(self):
        self.ad_timer = QTimer()
        self.ad_timer.timeout.connect(self.check_ads)
        self.ad_timer.start(60000)

    def init_waveform(self):
        self.waveform = WaveformWindow()

    def init_watchdog(self):
        self._watchdog_timer = QTimer()
        self._watchdog_timer.timeout.connect(self._check_listener_health)
        self._watchdog_timer.setInterval(1000)
        self._watchdog_timer.start()

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
            listener_path = os.path.join(os.path.dirname(__file__), "hotkey_listener.py")
            creation = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            self._listener_proc = subprocess.Popen(
                [sys.executable, listener_path, hotkey],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                creationflags=creation,
            )

            self._listener_queue = queue.Queue()
            self._listener_thread = threading.Thread(
                target=self._listener_read_loop, daemon=True
            )
            self._listener_thread.start()

            self._listener_reader = QTimer()
            self._listener_reader.timeout.connect(self._read_listener)
            self._listener_reader.setInterval(30)
            self._listener_reader.start()

            print(f"Hotkey listener: {hotkey}")
        except Exception as e:
            print(f"Listener error: {e}")

    def _listener_read_loop(self):
        proc = self._listener_proc
        if not proc or not proc.stdout:
            return
        try:
            for line in iter(proc.stdout.readline, ''):
                if line:
                    self._listener_queue.put(line.strip())
        except Exception:
            pass

    def _stop_listener(self):
        if self._listener_proc:
            try:
                self._listener_proc.terminate()
                self._listener_proc.wait(timeout=1)
            except Exception:
                try:
                    self._listener_proc.kill()
                except Exception:
                    pass
            self._listener_proc = None

    def _read_listener(self):
        if not hasattr(self, '_listener_queue'):
            return
        try:
            while True:
                line = self._listener_queue.get_nowait()
                if line.startswith("KEY_DOWN"):
                    self._hotkey_signal.emit("DOWN")
                elif line.startswith("KEY_UP"):
                    self._hotkey_signal.emit("UP")
                elif line.startswith("HEARTBEAT"):
                    self._last_heartbeat = time.time()
                    self._listener_alive = True
        except queue.Empty:
            pass

    def _check_listener_health(self):
        if self._listener_proc is None:
            return
        if self._listener_proc.poll() is not None:
            print("Listener process died, restarting...", flush=True)
            self._restart_listener()
            return
        if self._listener_alive and time.time() - self._last_heartbeat > 5:
            print("Listener heartbeat timeout, restarting...", flush=True)
            self._restart_listener()

    def _restart_listener(self):
        self._stop_listener()
        hotkey = self.settings.get("hotkey", "f9")
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
            self._recording_timeout = QTimer.singleShot(60000, self._force_stop_recording)

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
            log("TRANSCRIBE_START", f"frames={len(audio)} elapsed={elapsed:.1f}s")
            text = self.transcriber.transcribe(audio)
            log("TRANSCRIBE_DONE", f"text={repr(text[:80]) if text else 'EMPTY'}")
            self.signals.transcribing_finished.emit()
            if text:
                self.signals.text_ready.emit(text)
        else:
            reason = "no transcriber" if not self.transcriber else "empty audio"
            log("TRANSCRIBE_SKIP", reason)
            self.signals.transcribing_finished.emit()

    def on_text_ready(self, text):
        self._suppress_hotkey = True
        try:
            import pyperclip
            pyperclip.copy(text)
            QTimer.singleShot(100, lambda: self._do_paste(text))
        except Exception as e:
            print(f"Paste error: {e}")
            self._suppress_hotkey = False

    def _do_paste(self, text):
        try:
            is_terminal = _is_terminal()
            _paste_via_sendinput(text, auto_send=self.settings.get("auto_send"), is_terminal=is_terminal)
        except Exception as e:
            print(f"Paste error: {e}")
        finally:
            QTimer.singleShot(300, self._release_hotkey_suppress)

    def _release_hotkey_suppress(self):
        self._suppress_hotkey = False

    def on_recording_started(self):
        self.mic_indicator.set_color("#00ff88")
        self.tray.setIcon(self.create_mic_icon("#00ff88"))

    def on_recording_stopped(self):
        self.mic_indicator.set_color("#f7ff00")
        self.tray.setIcon(self.create_mic_icon("#f7ff00"))

    def on_transcribing_started(self):
        self.is_transcribing = True
        self.mic_indicator.set_color("#00f7ff")
        self.waveform.show_transcribing()

    def on_transcribing_finished(self):
        self.is_transcribing = False
        self.mic_indicator.set_color("#333")
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

    def start_hotkey_capture(self):
        self._capturing_hotkey = True
        self._captured_keys = set()
        self._hotkey_timer = QTimer()
        self._hotkey_timer.setSingleShot(True)
        self._hotkey_timer.setInterval(500)
        self._hotkey_timer.timeout.connect(self._finish_hotkey_capture)
        self.hotkey_btn.setText("Нажмите клавишу (или комбинацию)...")
        self.hotkey_btn.setStyleSheet("background-color: #00ff88; color: #000; border: 1px solid #00ff88; border-radius: 5px; font-weight: bold;")
        self.hotkey_btn.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.hotkey_btn and self._capturing_hotkey:
            if event.type() == event.Type.KeyPress:
                vk = event.nativeVirtualKey()
                self._captured_keys.add(vk)
                self._hotkey_timer.start()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if not self._capturing_hotkey:
            return super().keyPressEvent(event)
        vk = event.nativeVirtualKey()
        self._captured_keys.add(vk)
        self._hotkey_timer.start()

    def keyReleaseEvent(self, event):
        if not self._capturing_hotkey:
            return super().keyReleaseEvent(event)

    def _finish_hotkey_capture(self):
        self._capturing_hotkey = False
        VK_NAMES = {
            0x11: "ctrl", 0x10: "shift", 0x12: "alt",
            0x5B: "win", 0x5C: "win",
            0x41: "a", 0x42: "b", 0x43: "c", 0x44: "d", 0x45: "e",
            0x46: "f", 0x47: "g", 0x48: "h", 0x49: "i", 0x4A: "j",
            0x4B: "k", 0x4C: "l", 0x4D: "m", 0x4E: "n", 0x4F: "o",
            0x50: "p", 0x51: "q", 0x52: "r", 0x53: "s", 0x54: "t",
            0x55: "u", 0x56: "v", 0x57: "w", 0x58: "x", 0x59: "y", 0x5A: "z",
            0x70: "f1", 0x71: "f2", 0x72: "f3", 0x73: "f4",
            0x74: "f5", 0x75: "f6", 0x76: "f7", 0x77: "f8",
            0x78: "f9", 0x79: "f10", 0x7A: "f11", 0x7B: "f12",
            0x20: "space", 0x0D: "enter", 0x1B: "esc",
            0x09: "tab", 0x14: "capslock",
        }
        parts = []
        for vk in sorted(self._captured_keys):
            name = VK_NAMES.get(vk, chr(vk) if 32 <= vk < 127 else f"vk{vk}")
            parts.append(name)
        combo = "+".join(parts)
        self.settings.set("hotkey", combo)
        self.hotkey_btn.setText(combo.upper())
        self.hotkey_btn.setStyleSheet("")
        self._start_listener(combo)

    def update_model_list(self):
        self.model_list.clear()
        for model in self.settings.get("models", []):
            name = model["name"]
            active = "● " if name == self.settings.get("active_model") else "○ "
            size = f" ({model['size']})" if model.get("size") else ""
            self.model_list.addItem(f"{active}{name}{size}")

        count = self.model_list.count()
        row_h = self.model_list.sizeHintForRow(0)
        if row_h > 0:
            self.model_list.setFixedHeight(min(count, 5) * row_h + 4)

    def add_model(self):
        path = QFileDialog.getExistingDirectory(self, "Выберите папку с моделью")
        if path:
            name = os.path.basename(path)
            model_type = "sherpa-onnx"
            if "whisper" in name.lower():
                model_type = "whisper"
            elif "vosk" in name.lower():
                model_type = "vosk"

            model = {
                "name": name,
                "path": path,
                "type": model_type,
                "language": "ru",
                "size": ""
            }
            self.settings.add_model(model)
            self.update_model_list()

    def remove_model(self):
        row = self.model_list.currentRow()
        if row >= 0:
            models = self.settings.get("models", [])
            if row < len(models):
                name = models[row]["name"]
                reply = QMessageBox.question(self, "Удалить", f"Удалить {name}?")
                if reply == QMessageBox.StandardButton.Yes:
                    self.settings.remove_model(name)
                    self.update_model_list()

    def set_active_model(self):
        row = self.model_list.currentRow()
        if row >= 0:
            models = self.settings.get("models", [])
            if row < len(models):
                name = models[row]["name"]
                self.settings.set("active_model", name)
                self.update_model_list()
                self.load_active_model()

    def load_active_model(self):
        active_name = self.settings.get("active_model")
        models = self.settings.get("models", [])
        for model in models:
            if model["name"] == active_name:
                self.transcriber = Transcriber(model)
                break

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
