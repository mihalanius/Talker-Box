import sys
import os
import time
import threading
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

        w = self.width()
        h = self.height()
        s = self._corner_size

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

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(15, 20, 10, 10)

    def layout(self):
        return self._layout

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        s = self._corner_size

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

        painter.end()

class Signals(QObject):
    text_ready = pyqtSignal(str)
    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = SettingsManager()
        self.recorder = Recorder()
        self.transcriber = None
        self.ad_manager = AdManager()
        self.signals = Signals()
        self.is_recording = False
        self.hold_mode = False
        
        self.signals.text_ready.connect(self.on_text_ready)
        self.signals.recording_started.connect(self.on_recording_started)
        self.signals.recording_stopped.connect(self.on_recording_stopped)
        
        self.init_ui()
        self.init_tray()
        self.init_hotkey()
        self.load_active_model()
        self.init_ad_timer()
        self.init_waveform()
        self.init_level_monitor()
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
                border: 1px solid #00f7ff;
                border-radius: 3px;
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
        self.hotkey_btn = QPushButton(self.settings.get("hotkey", "ctrl+win").upper())
        self.hotkey_btn.setFixedHeight(30)
        self.hotkey_btn.clicked.connect(self.start_hotkey_capture)
        self._capturing_hotkey = False
        hotkey_layout.addWidget(self.hotkey_btn)
        settings_layout.addLayout(hotkey_layout)
        
        layout.addWidget(settings_group)
        
        model_group = NeonGroupBox("Модели")
        model_layout = model_group.layout()
        
        self.model_list = QListWidget()
        self.update_model_list()
        model_layout.addWidget(self.model_list)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        btn_style = """
            QPushButton {
                color: #00ff88;
                background: transparent;
                border: 1px solid #00ff88;
                border-radius: 2px;
                font: 10px 'Segoe UI';
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
        
        self.mic_indicator = QLabel()
        self.mic_indicator.setFixedHeight(5)
        self.mic_indicator.setStyleSheet("background-color: #333;")
        layout.addWidget(self.mic_indicator)
        
        self.ad_banner = QLabel()
        self.ad_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ad_banner.setFixedHeight(100)
        self.ad_banner.setStyleSheet("background-color: #16213e; border: 1px solid #333; border-radius: 5px;")
        self.ad_banner.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ad_banner.mousePressEvent = self.on_ad_banner_click
        layout.addWidget(self.ad_banner)
        self.update_ad_banner()
        
        version_label = QLabel("Версия 1.12")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #00ff88; font-size: 11px; padding: 5px;")
        layout.addWidget(version_label)
    
    def init_ad_timer(self):
        self.ad_timer = QTimer()
        self.ad_timer.timeout.connect(self.check_ads)
        self.ad_timer.start(60000)
    
    def init_waveform(self):
        self.waveform = WaveformWindow()
    
    def init_level_monitor(self):
        pass
    
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
        try:
            import ctypes
            self._user32 = ctypes.windll.user32
            self._key_states = {}
            self._poll_timer = QTimer()
            self._poll_timer.timeout.connect(self._poll_hotkey)
            self._poll_timer.setInterval(50)
            self._poll_timer.start()
            self._hotkey_vks = self._parse_hotkey(self.settings.get("hotkey", "ctrl+win"))
        except Exception as e:
            print(f"Hotkey error: {e}")

    def _parse_hotkey(self, hotkey_str):
        VK_MAP = {
            "ctrl": 0x11, "shift": 0x10, "alt": 0x12,
            "win": 0x5B, "lwin": 0x5B, "rwin": 0x5C,
            "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
            "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
            "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
            "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
            "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59, "z": 0x5A,
            "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
            "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
            "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
            "space": 0x20, "enter": 0x0D, "esc": 0x1B,
            "tab": 0x09, "capslock": 0x14,
        }
        vks = []
        for part in hotkey_str.lower().split("+"):
            part = part.strip()
            vk = VK_MAP.get(part)
            if vk:
                vks.append(vk)
            elif len(part) == 1:
                vks.append(ord(part.upper()))
        return vks

    def _poll_hotkey(self):
        try:
            all_pressed = all(
                bool(self._user32.GetAsyncKeyState(vk) & 0x8000)
                for vk in self._hotkey_vks
            ) if self._hotkey_vks else False

            prev = self._key_states.get("hotkey", False)
            self._key_states["hotkey"] = all_pressed

            if all_pressed and not prev:
                if self.settings.get("mode") == "toggle":
                    if self.is_recording:
                        self.stop_recording()
                    else:
                        self.start_recording()
                else:
                    if not self.is_recording:
                        self.start_recording()
                        self.hold_mode = True

            if not all_pressed and prev:
                if self.hold_mode and self.is_recording:
                    self.hold_mode = False
                    self.stop_recording()
        except:
            pass
    
    def start_recording(self):
        if not self.is_recording:
            self.is_recording = True
            self.recorder.start()
            self.signals.recording_started.emit()
            self.waveform.show_wave()
            play_start_sound()
            self._recording_timeout = QTimer.singleShot(60000, self._force_stop_recording)
    
    def _force_stop_recording(self):
        if self.is_recording:
            self.stop_recording()
    
    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            audio = self.recorder.stop()
            self.signals.recording_stopped.emit()
            self.waveform.hide_wave()
            play_stop_sound()
            threading.Thread(target=self.transcribe_audio, args=(audio,), daemon=True).start()
    
    def transcribe_audio(self, audio):
        if self.transcriber and len(audio) > 0:
            text = self.transcriber.transcribe(audio)
            if text:
                self.signals.text_ready.emit(text)
    
    def on_text_ready(self, text):
        import pyperclip
        pyperclip.copy(text)
        
        try:
            import keyboard
            keyboard.press_and_release('ctrl+v')
            time.sleep(0.1)
            
            if self.settings.get("auto_send"):
                keyboard.press_and_release('enter')
        except:
            pass
    
    def on_recording_started(self):
        self.mic_indicator.setStyleSheet("background-color: #00ff88;")
        self.tray.setIcon(self.create_mic_icon("#00ff88"))
    
    def on_recording_stopped(self):
        self.mic_indicator.setStyleSheet("background-color: #ff8800;")
        self.tray.setIcon(self.create_mic_icon("#ff8800"))
        QTimer.singleShot(1000, lambda: self.mic_indicator.setStyleSheet("background-color: #333;"))
    
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

        key = event.key()
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
        self.init_hotkey()
    
    def on_waveform_changed(self, state):
        pass
    
    def update_model_list(self):
        self.model_list.clear()
        for model in self.settings.get("models", []):
            name = model["name"]
            active = "● " if name == self.settings.get("active_model") else "○ "
            size = f" ({model['size']})" if model.get("size") else ""
            self.model_list.addItem(f"{active}{name}{size}")
    
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
