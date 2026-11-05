# -*- coding: utf-8 -*-
"""Рекламная полоска под окном программы (бесплатная версия).

Идея и формат данных взяты из расширения Quick Bar: на сервере лежит ads.json
со списком баннеров (видео или картинка + ссылка), программа показывает первый
доступный и открывает ссылку по клику. Видео играет беззвучно и по кругу.

Ключи JSON (совместимы с Quick Bar и с ad_manager):
    {"bar": [{"video": "...mp4", "text": "...", "link": "https://..."}, ...]}
Если баннер не загрузился — показываем текст и ссылку.
"""
import os

from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import (QDesktopServices, QMovie, QPixmap, QCursor, QPainter,
                         QPainterPath, QPen, QColor, QRegion)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

BANNER_HEIGHT = 80      # высота полоски, px


class AdMarkWindow(QWidget):
    """Плашка «Реклама» отдельным прозрачным окном.

    Видеоповерхность (QVideoWidget) рисуется поверх обычных дочерних виджетов,
    поэтому плашку внутри полоски не видно на видео. Отдельное окно поверх
    решает это для любого баннера — и для видео, и для картинки.
    """

    def __init__(self, parent=None):
        super().__init__(parent,
                         Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.WindowDoesNotAcceptFocus |
                         Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("Реклама", self)
        # как .ad-label в Quick Bar: прозрачный контейнер, простой светло-серый текст, без тени
        self.label.setStyleSheet(
            "QLabel { color: #b0a88c; font-size: 8px; letter-spacing: 0.5px;"
            " background: transparent; border: none; padding: 0; }")
        self.label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        lay.addWidget(self.label)
        self.adjustSize()


class AdBanner(QWidget):
    """Полоска рекламы: «Реклама» + видео/картинка/текст. Клик открывает ссылку."""

    clicked = pyqtSignal(str)     # ссылка

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(BANNER_HEIGHT)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # фон и рамку рисуем сами в paintEvent — со скруглением
        self.setStyleSheet("QWidget#adBanner { background: transparent; }")
        self.setObjectName("adBanner")

        self._ad = {}
        self._movie = None
        self._player = None
        self._audio = None
        self._video = None
        self._nam = QNetworkAccessManager(self)
        self._reply = None

        lay = QHBoxLayout(self)
        # поля как в Quick Bar: 8 по бокам, 6 сверху и 8 снизу — рамка вокруг видео
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(0)

        # плашка «Реклама» — отдельным окном поверх видео (см. AdMarkWindow).
        # родитель — главное окно: тогда плашка гарантированно выше него и едет вместе с ним
        self._mark = AdMarkWindow(self.window())
        self._mark.hide()

        self._content = QWidget(self)
        self._content.setStyleSheet("background: transparent;")
        self._content_lay = QVBoxLayout(self._content)
        self._content_lay.setContentsMargins(0, 0, 0, 0)
        self._content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        self._text = QLabel("", self)
        self._text.setStyleSheet("QLabel { color: #444; font-size: 11px;"
                                 " background: transparent; }")
        self._text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(self._content, 1)
        self._content_lay.addWidget(self._text)

        self._hide_media()
        self.hide()
        # геометрия полоски меняется после раскладки — плашку позиционируем ещё и по таймеру
        self._mark_timer = QTimer(self)
        self._mark_timer.timeout.connect(self._place_mark)
        self._mark_timer.start(600)

    def _place_mark(self):
        """Плашка «Реклама» — в правом верхнем углу полоски (отдельным окном)."""
        if not self.isVisible() or self.width() < 100:
            self._mark.hide()
            return
        self._mark.adjustSize()
        # позицию считаем от области видео, а не от всего виджета — иначе уезжает к краю
        r = self._content.geometry()
        p = self.mapToGlobal(QPoint(r.right() - self._mark.width() - 4, r.top() + 3))
        self._mark.move(p)
        self._mark.show()
        self._mark.raise_()
        try:
            from logger import log
            log("AD_MARK", f"pos={p.x()},{p.y()} size={self._mark.width()}x{self._mark.height()}")
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._place_mark()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._mark.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, "_mark", None) is not None:
            self._place_mark()
            self._mark.raise_()
        self._apply_clip()

    def _apply_clip(self):
        """Обрезаем содержимое по скруглённому прямоугольнику (как overflow:hidden)."""
        try:
            r = self._content.geometry()
            rounded = QPainterPath()
            rounded.addRoundedRect(0, 0, r.width(), r.height(), 8, 8)
            self._content.setMask(QRegion(rounded.toFillPolygon().toPolygon()))
        except Exception:
            pass

    def paintEvent(self, event):
        """Фон и окантовка полоски — цвета фона программы (как .ad-strip в Quick Bar)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#d9d9d6")          # цвет фона программы
        painter.setPen(QPen(bg, 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 8, 8)
        painter.end()

    # ---------- показ баннера ----------
    def set_ad(self, ad):
        """Показать баннер: {'video'|'image'|'gif': url, 'text': str, 'link': str}."""
        self._clear_media()
        self._ad = dict(ad or {})
        link = str(self._ad.get("link", "")).strip()
        if not link:
            self.hide()          # без ссылки реклама не нужна
            return
        self._text.setText(str(self._ad.get("text", "")))
        self._text.hide()
        self.show()

        video = self._ad.get("video") or ""
        image = self._ad.get("image") or ""
        gif = self._ad.get("gif") or ""
        if video:
            self._play_video(video)
        elif gif:
            self._play_gif(gif)
        elif image:
            self._load_image(image)
        else:
            self._text.show()    # только текст

    def _add_media(self, widget):
        widget.setStyleSheet("background: transparent;")
        widget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._content_lay.addWidget(widget)
        widget.installEventFilter(self)
        self._mark.raise_()
        self._apply_clip()

    def _hide_media(self):
        pass

    def _play_video(self, url):
        self._video = QVideoWidget(self)
        self._video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self._add_media(self._video)

        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(0.0)          # беззвучно
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video)
        self._player.setLoops(QMediaPlayer.Loops.Infinite)
        self._player.errorOccurred.connect(self._on_video_error)
        self._player.setSource(QUrl(url) if "://" in url else QUrl.fromLocalFile(
            os.path.abspath(url)))
        self._player.play()

    def _play_gif(self, url):
        if "://" in url:
            self._download(url, self._on_gif_bytes)
            return
        self._start_movie(os.path.abspath(url))

    def _start_movie(self, path):
        self._movie = QMovie(path)
        self._movie.setScaledSize(QSize(BANNER_HEIGHT * 4, BANNER_HEIGHT - 8))
        label = QLabel(self)
        label.setMovie(self._movie)
        self._add_media(label)
        self._movie.start()

    def _load_image(self, url):
        if "://" in url:
            self._download(url, self._on_image_bytes)
            return
        pix = QPixmap(os.path.abspath(url))
        self._show_pixmap(pix)

    def _show_pixmap(self, pix):
        if pix.isNull():
            self._text.show()
            return
        label = QLabel(self)
        label.setPixmap(pix.scaledToHeight(BANNER_HEIGHT - 6,
                                           Qt.TransformationMode.SmoothTransformation))
        self._add_media(label)

    def _download(self, url, on_done):
        """Асинхронно тянем картинку/гифку (видео играет прямо по URL)."""
        req = QNetworkRequest(QUrl(url))
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        self._reply = self._nam.get(req)
        self._reply.finished.connect(lambda: on_done(self._reply.readAll()))

    def _on_image_bytes(self, data):
        pix = QPixmap()
        if not data or not pix.loadFromData(bytes(data)):
            self._text.show()
            return
        self._show_pixmap(pix)

    def _on_gif_bytes(self, data):
        if not data:
            self._text.show()
            return
        # QMovie из памяти не умеет — пишем во временный файл
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".gif")
        os.close(fd)
        with open(path, "wb") as f:
            f.write(bytes(data))
        self._start_movie(path)

    def _on_video_error(self, *_):
        self._text.show()          # видео не пошло — показываем текст

    # ---------- клик ----------
    def eventFilter(self, obj, event):
        if event.type() == event.Type.MouseButtonPress:
            self._open_link()
            return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        self._open_link()

    def _open_link(self):
        link = str(self._ad.get("link", "")).strip()
        if link:
            QDesktopServices.openUrl(QUrl(link))
            self.clicked.emit(link)

    # ---------- очистка ----------
    def _clear_media(self):
        if self._movie is not None:
            self._movie.stop()
            self._movie = None
        if self._player is not None:
            self._player.stop()
            self._player.setSource(QUrl())
            self._player = None
        if self._audio is not None:
            self._audio = None
        if self._video is not None:
            self._video.deleteLater()
            self._video = None
        # убираем все виджеты контента, кроме текста
        while self._content_lay.count() > 1:
            item = self._content_lay.takeAt(1)
            w = item.widget()
            if w is not None:
                w.deleteLater()
