import math
import random
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor


class WaveformWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(200, 30)
        self.phase = 0.0
        self.mode = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.setInterval(33)
        self._dots = [0.0, 0.0, 0.0]
        self._dot_targets = [1.0, 0.5, 0.8]
        self._spinner_angle = 0.0

    def _position_above_taskbar(self):
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2
            y = geo.height() - self.height() - 10
            self.move(x, y)

    def show_recording(self):
        self.mode = "recording"
        self.phase = 0.0
        self._position_above_taskbar()
        self.show()
        self.timer.start()

    def show_transcribing(self):
        self.mode = "transcribing"
        self.phase = 0.0
        self._dots = [0.0, 0.0, 0.0]
        self._dot_targets = [1.0, 0.5, 0.8]
        self._spinner_angle = 0.0
        self._position_above_taskbar()
        self.show()
        self.timer.start()

    def hide_wave(self):
        self.mode = None
        self.timer.stop()
        self.hide()

    def tick(self):
        self.phase += 0.4
        if self.mode == "transcribing":
            self._spinner_angle = (self._spinner_angle + 8) % 360
            for i in range(3):
                if abs(self._dots[i] - self._dot_targets[i]) < 0.05:
                    self._dot_targets[i] = random.uniform(0.3, 1.0)
                self._dots[i] += (self._dot_targets[i] - self._dots[i]) * 0.12
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2

        p.setBrush(QColor(15, 15, 30, 200))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, w, h)

        if self.mode == "recording":
            self._paint_recording(p, w, h, cx, cy)
        elif self.mode == "transcribing":
            self._paint_transcribing(p, w, h, cx, cy)

        p.end()

    def _paint_recording(self, p, w, h, cx, cy):
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

    def _paint_transcribing(self, p, w, h, cx, cy):
        radius = 10
        dot_r = 4

        for i in range(3):
            angle = math.radians(self._spinner_angle + i * 120)
            dx = cx + radius * math.cos(angle) - dot_r / 2
            dy = cy + radius * math.sin(angle) - dot_r / 2
            alpha = int(100 + self._dots[i] * 155)
            p.setBrush(QColor(0, 200, 255, alpha))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(dx), int(dy), int(dot_r), int(dot_r))

        pulse = abs(math.sin(self.phase * 0.8)) * 0.4 + 0.6
        pulse_r = int(16 + pulse * 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 200, 255, 40))
        p.drawEllipse(int(cx - pulse_r), int(cy - pulse_r), pulse_r * 2, pulse_r * 2)
