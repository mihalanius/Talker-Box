"""Фоновая загрузка модели распознавания речи"""

from PyQt6.QtCore import QThread, pyqtSignal


class ModelLoader(QThread):
    """Загрузка модели в отдельном потоке"""
    
    finished = pyqtSignal(object)  # Загруженный транскрибер
    error = pyqtSignal(str)  # Текст ошибки
    
    def __init__(self, model_config, parent=None):
        super().__init__(parent)
        self.model_config = model_config
    
    def run(self):
        try:
            from transcriber import Transcriber
            transcriber = Transcriber(self.model_config)
            if transcriber.recognizer:
                self.finished.emit(transcriber)
            else:
                self.error.emit("Модель не загружена")
        except Exception as e:
            self.error.emit(str(e))
