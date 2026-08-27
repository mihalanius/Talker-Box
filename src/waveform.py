import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRect
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
        
        self.setFixedSize(300, 100)
        self.move_to_center()
        
        self.level = 0.0
        self.phase = 0.0
        self.bars = 40
        self.is_visible = False
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)
        self.timer.setInterval(16)
    
    def move_to_center(self):
        screen = self.screen()
        if screen:
            geo = screen.geometry()
            x = (geo.width() - self.width()) // 2
            y = (geo.height() - self.height()) // 2
            self.move(x, y)
    
    def set_level(self, level):
        self.level = min(1.0, max(0.0, level))
    
    def show_wave(self):
        self.is_visible = True
        self.show()
        self.timer.start()
    
    def hide_wave(self):
        self.is_visible = False
        self.timer.stop()
        self.hide()
    
    def animate(self):
        self.phase += 0.15
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setBrush(QColor(26, 26, 46, 180))
        painter.setPen(QPen(QColor(0, 247, 255, 100), 1))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 10, 10)
        
        bar_width = self.width() / (self.bars * 1.5)
        gap = bar_width * 0.5
        total_width = self.bars * (bar_width + gap)
        start_x = (self.width() - total_width) / 2
        
        for i in range(self.bars):
            x = start_x + i * (bar_width + gap)
            
            wave = math.sin(self.phase + i * 0.3) * 0.3
            wave += math.sin(self.phase * 1.5 + i * 0.2) * 0.2
            wave += math.sin(self.phase * 0.7 + i * 0.5) * 0.1
            
            bar_height = abs(wave) * self.level * self.height() * 0.6
            bar_height = max(3, bar_height)
            
            y = (self.height() - bar_height) / 2
            
            color = QColor(0, 255, 136, 200)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                int(x), int(y),
                int(bar_width), int(bar_height),
                2, 2
            )
        
        painter.end()
