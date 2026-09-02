import math
import random
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen

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

        self.setFixedSize(300, 60)
        self._center_on_screen()

        self.phase = 0.0
        self.bars = 30
        self.is_visible = False
        self._target_heights = [0.0] * self.bars
        self._current_heights = [0.0] * self.bars

        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.timer.setInterval(30)

    def _center_on_screen(self):
        screen = self.screen()
        if screen:
            geo = screen.geometry()
            x = (geo.width() - self.width()) // 2
            y = geo.height() - self.height() - 60
            self.move(x, y)

    def show_wave(self):
        self.is_visible = True
        self.phase = 0.0
        self._target_heights = [random.uniform(0.2, 1.0) for _ in range(self.bars)]
        self.show()
        self.timer.start()

    def hide_wave(self):
        self.is_visible = False
        self.timer.stop()
        self.hide()

    def animate(self):
        self.phase += 0.2

        if random.random() < 0.3:
            idx = random.randint(0, self.bars - 1)
            self._target_heights[idx] = random.uniform(0.15, 1.0)

        for i in range(self.bars):
            wave = math.sin(self.phase + i * 0.4) * 0.4
            wave += math.sin(self.phase * 1.7 + i * 0.25) * 0.25
            wave += math.sin(self.phase * 0.6 + i * 0.6) * 0.15
            target = (abs(wave) * 0.5 + self._target_heights[i] * 0.5)
            self._current_heights[i] += (target - self._current_heights[i]) * 0.3

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(QColor(20, 20, 40, 200))
        painter.setPen(QPen(QColor(0, 255, 136, 60), 1))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 8, 8)

        bar_w = self.width() / (self.bars * 1.4)
        gap = bar_w * 0.4
        total = self.bars * (bar_w + gap)
        start_x = (self.width() - total) / 2

        for i in range(self.bars):
            x = start_x + i * (bar_w + gap)
            h = max(3, self._current_heights[i] * self.height() * 0.7)
            y = (self.height() - h) / 2

            g = int(180 + self._current_heights[i] * 75)
            color = QColor(0, g, 136, 220)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(int(x), int(y), int(bar_w), int(h), 2, 2)

        painter.end()
