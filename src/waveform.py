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
        self.setFixedSize(300, 50)
        self.phase = 0.0
        self.active = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.setInterval(40)

    def show_wave(self):
        self.phase = 0.0
        self.active = True
        self.show()
        self.timer.start()

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
        p.fillRect(self.rect(), QColor(15, 15, 30, 200))

        w = self.width()
        h = self.height()
        n = 25
        bw = w / (n * 1.5)
        gap = bw * 0.5
        total = n * (bw + gap)
        sx = (w - total) / 2

        for i in range(n):
            v = math.sin(self.phase + i * 0.5) * 0.6
            v += math.sin(self.phase * 2.1 + i * 0.35) * 0.4
            v += math.sin(self.phase * 0.8 + i * 0.7) * 0.25
            bh = max(4, abs(v) * h * 0.85)
            x = sx + i * (bw + gap)
            y = (h - bh) / 2
            c = int(140 + abs(v) * 115)
            p.setBrush(QColor(0, c, 100, 230))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(int(x), int(y), int(bw), int(bh), 2, 2)
        p.end()
