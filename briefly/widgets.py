"""Small, reusable Qt components and vector artwork."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from .style import INK, TEAL


def label(text: str, name: str = "", wrap: bool = False) -> QLabel:
    item = QLabel(text)
    item.setObjectName(name)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setWordWrap(wrap)
    if wrap:
        item.setMinimumWidth(0)
    return item


def button(text: str, name: str, callback=None) -> QPushButton:
    item = QPushButton(text)
    item.setObjectName(name)
    item.setCursor(Qt.CursorShape.PointingHandCursor)
    if callback:
        item.clicked.connect(callback)
    return item


def icon(kind: str, color: str = INK, size: int = 20) -> QIcon:
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 24, size / 24)
    painter.setPen(QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if kind == "bookmark":
        path = QPainterPath(QPointF(6, 4))
        for point in (QPointF(18, 4), QPointF(18, 21), QPointF(12, 16), QPointF(6, 21)):
            path.lineTo(point)
        path.closeSubpath()
        painter.drawPath(path)
    elif kind == "news":
        painter.drawRoundedRect(QRectF(3, 4, 18, 16), 2, 2)
        painter.drawRect(QRectF(6, 7, 5, 5))
        for y in (8, 11):
            painter.drawLine(QPointF(14, y), QPointF(18, y))
        for y in (15, 17):
            painter.drawLine(QPointF(6, y), QPointF(18, y))
    elif kind == "sliders":
        for y, x in ((6, 8), (12, 16), (18, 10)):
            painter.drawLine(QPointF(4, y), QPointF(20, y))
            painter.setBrush(QColor(color))
            painter.drawEllipse(QPointF(x, y), 2, 2)
    elif kind == "external":
        painter.drawLine(QPointF(8, 16), QPointF(19, 5))
        painter.drawLine(QPointF(12, 5), QPointF(19, 5))
        painter.drawLine(QPointF(19, 5), QPointF(19, 12))
        painter.drawLine(QPointF(5, 9), QPointF(5, 19))
        painter.drawLine(QPointF(5, 19), QPointF(15, 19))
    elif kind == "refresh":
        painter.drawArc(QRectF(4, 4, 16, 16), 40 * 16, 285 * 16)
        painter.drawLine(QPointF(20, 4), QPointF(20, 10))
        painter.drawLine(QPointF(14, 10), QPointF(20, 10))
    elif kind == "spark":
        path = QPainterPath(QPointF(12, 2))
        for x, y in ((14, 9), (22, 12), (14, 14), (12, 22), (10, 14), (2, 12), (10, 9)):
            path.lineTo(x, y)
        path.closeSubpath()
        painter.drawPath(path)
    else:
        painter.drawEllipse(QRectF(4, 4, 16, 16))
        painter.drawLine(QPointF(12, 10), QPointF(12, 17))
        painter.drawPoint(QPointF(12, 7))
    painter.end()
    return QIcon(pixmap)


class BrandMark(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(38, 38)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#e7bd85"))
        painter.drawRoundedRect(QRectF(1, 1, 36, 36), 10, 10)
        painter.setPen(QPen(QColor("#182c33"), 2.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for y, width in ((11, 15), (17, 15), (23, 10), (29, 6)):
            painter.drawLine(QPointF(11, y), QPointF(11 + width, y))


class WorldArtwork(QWidget):
    """Resolution-independent illustration, with no remote asset requests."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(230, 205)
        self.setMaximumWidth(320)
        self.setAccessibleName("An illustrated globe with orbiting news pages")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        scale = min(self.width() / 300, self.height() / 225)
        painter.scale(scale, scale)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#e2decf"))
        painter.drawEllipse(QRectF(-116, -96, 218, 200))
        painter.setPen(QPen(QColor("#c9cdbb"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(-130, -72, 267, 144))
        painter.save()
        painter.rotate(-29)
        painter.drawEllipse(QRectF(-129, -68, 258, 136))
        painter.restore()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#29685f"))
        painter.drawEllipse(QRectF(-79, -79, 158, 158))
        painter.setPen(QPen(QColor("#71a195"), 1.1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for w in (50, 108, 158):
            painter.drawEllipse(QRectF(-w / 2, -79, w, 158))
        for h in (48, 106):
            painter.drawEllipse(QRectF(-79, -h / 2, 158, h))
        painter.drawLine(QPointF(-79, 0), QPointF(79, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#c1ccb0"))
        continent = QPainterPath(QPointF(-37, -47))
        for x, y in ((-16, -58), (5, -47), (12, -25), (3, -13), (21, -4), (9, 11), (-9, 18), (-15, 39), (-30, 44), (-39, 21), (-30, 6), (-48, -8), (-43, -26)):
            continent.lineTo(x, y)
        continent.closeSubpath()
        painter.drawPath(continent)
        painter.setBrush(QColor("#dba984"))
        painter.drawEllipse(QPointF(111, -43), 9, 9)
        painter.setBrush(QColor("#9baa8c"))
        painter.drawEllipse(QPointF(-116, 31), 5, 5)
        for x, y, angle in ((-105, -50, -14), (68, 48, 12)):
            painter.save()
            painter.translate(x, y)
            painter.rotate(angle)
            painter.setBrush(QColor("#fbfaf3"))
            painter.setPen(QPen(QColor("#d4d6c8"), 1))
            painter.drawRoundedRect(QRectF(-30, -26, 65, 48), 6, 6)
            painter.setPen(QPen(QColor("#bd5d40"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(-19, -13), QPointF(19, -13))
            painter.setPen(QPen(QColor("#a8b4a7"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for yy, width in ((-3, 34), (5, 38), (13, 23)):
                painter.drawLine(QPointF(-19, yy), QPointF(-19 + width, yy))
            painter.restore()


class Spinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(26, 26)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.advance)

    def advance(self):
        self.angle = (self.angle + 14) % 360
        self.update()

    def showEvent(self, event):
        self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#dce5da"), 2.5))
        painter.drawEllipse(QRectF(4, 4, 18, 18))
        painter.setPen(QPen(QColor(TEAL), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(4, 4, 18, 18), -self.angle * 16, 110 * 16)
