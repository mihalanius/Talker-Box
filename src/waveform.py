import math
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
        self.setFixedSize(150, 25)
        self.phase = 0.0
        self.active = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.setInterval(40)

    def show_wave(self):
        self.phase = 0.0
        self.active = True
        self._position_above_taskbar()
        self.show()
        self.timer.start()

    def _position_above_taskbar(self):
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2
            y = geo.height() - self.height() - 10
            self.move(x, y)

    def hide_wave(self):
        self.active = False
        self.timer.stop()
        self.hide()

    def tick(self):
        self.phase += 0.5
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(15, 15, 30, 200))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, self.width(), self.height())

        w = self.width()
        h = self.height()
        n = 15
        bw = w / (n * 1.8)
        gap = bw * 0.4
        total = n * (bw + gap)
        sx = (w - total) / 2

        for i in range(n):
            v = math.sin(self.phase + i * 0.6) * 0.6
            v += math.sin(self.phase * 2.1 + i * 0.4) * 0.4
            v += math.sin(self.phase * 0.8 + i * 0.8) * 0.25
            bh = max(2, abs(v) * h * 0.6)
            x = sx + i * (bw + gap)
            y = (h - bh) / 2
            c = int(140 + abs(v) * 115)
            p.setBrush(QColor(0, c, 100, 230))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(int(x), int(y), int(bw), int(bh), 1, 1)
        p.end()
