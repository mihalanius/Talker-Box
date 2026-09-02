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
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QBrush, QFont, QAction, QColor
from recorder import Recorder
from transcriber import Transcriber
from settings_manager import SettingsManager
from ad_manager import AdManager
from waveform import WaveformWindow
from sounds import play_start_sound, play_stop_sound

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
        self.setFixedSize(400, 450)
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a2e; }
            QLabel { color: #eee; }
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
            QCheckBox { color: #eee; }
            QGroupBox {
                color: #00f7ff;
                border: 1px solid #00f7ff;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
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
        
        settings_group = QGroupBox("Настройки")
        settings_layout = QVBoxLayout()
        
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
        self.hotkey_input = QLineEdit(self.settings.get("hotkey"))
        self.hotkey_input.setPlaceholderText("ctrl+win")
        self.hotkey_input.returnPressed.connect(self.on_hotkey_changed)
        hotkey_layout.addWidget(self.hotkey_input)
        settings_layout.addLayout(hotkey_layout)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        model_group = QGroupBox("Модели")
        model_layout = QVBoxLayout()
        
        self.model_list = QListWidget()
        self.update_model_list()
        model_layout.addWidget(self.model_list)
        
        btn_layout = QHBoxLayout()
        self.add_model_btn = QPushButton("+ Добавить")
        self.add_model_btn.clicked.connect(self.add_model)
        btn_layout.addWidget(self.add_model_btn)
        
        self.remove_model_btn = QPushButton("- Удалить")
        self.remove_model_btn.clicked.connect(self.remove_model)
        btn_layout.addWidget(self.remove_model_btn)
        
        self.set_active_btn = QPushButton("Выбрать")
        self.set_active_btn.clicked.connect(self.set_active_model)
        btn_layout.addWidget(self.set_active_btn)
        
        model_layout.addLayout(btn_layout)
        model_group.setLayout(model_layout)
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
    
    def init_ad_timer(self):
        self.ad_timer = QTimer()
        self.ad_timer.timeout.connect(self.check_ads)
        self.ad_timer.start(60000)
    
    def init_waveform(self):
        self.waveform = WaveformWindow()
    
    def init_level_monitor(self):
        self.level_timer = QTimer()
        self.level_timer.timeout.connect(self.update_level)
        self.level_timer.setInterval(33)
    
    def update_level(self):
        if self.is_recording and self.recorder.is_recording:
            audio = self.recorder.get_audio()
            if len(audio) > 0:
                import numpy as np
                level = np.abs(audio).mean() / 32768.0
                self.waveform.set_level(level * 3)
            else:
                self.waveform.set_level(0.1)
    
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
        except Exception as e:
            print(f"Hotkey error: {e}")

    def _poll_hotkey(self):
        try:
            VK_CONTROL = 0x11
            VK_LWIN = 0x5B
            VK_RWIN = 0x5C

            ctrl_pressed = bool(self._user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
            win_pressed = bool(self._user32.GetAsyncKeyState(VK_LWIN) & 0x8000) or \
                          bool(self._user32.GetAsyncKeyState(VK_RWIN) & 0x8000)

            hotkey_down = ctrl_pressed and win_pressed
            prev = self._key_states.get("hotkey", False)
            self._key_states["hotkey"] = hotkey_down

            if hotkey_down and not prev:
                if self.settings.get("mode") == "toggle":
                    if self.is_recording:
                        self.stop_recording()
                    else:
                        self.start_recording()
                else:
                    if not self.is_recording:
                        self.start_recording()
                        self.hold_mode = True

            if not hotkey_down and prev:
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
            self.level_timer.start()
            play_start_sound()
    
    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            audio = self.recorder.stop()
            self.signals.recording_stopped.emit()
            self.waveform.hide_wave()
            self.level_timer.stop()
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
    
    def on_hotkey_changed(self):
        hotkey = self.hotkey_input.text().strip()
        if hotkey:
            self.settings.set("hotkey", hotkey)
    
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
