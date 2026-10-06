"""Code-native placeholder artwork. Replace with production PNG frames at any time."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPolygonF

from ..domain.emotion import Emotion


SIZE = 320


def render_frame(
    kind: str, state: Emotion, index: int, count: int = 12, source: QImage | None = None
) -> QImage:
    image = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    phase = math.sin(index * math.tau / count)
    painter.translate(160, 180 + phase * (7 if state == Emotion.HAPPY else 2))
    if state == Emotion.ANGRY:
        painter.rotate(phase * 4)
    elif state == Emotion.SLEEPY:
        painter.rotate(-7 + phase)
    painter.scale(1.0 + phase * 0.009, 1.0 - phase * 0.014)
    if source is not None:
        scaled = source.scaled(
            250, 250, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        painter.drawImage(QPointF(-scaled.width() / 2, -scaled.height() / 2), scaled)
    else:
        fur = QColor("#eadfff" if kind == "rabbit" else "#ffe1a6")
        ink = QColor("#514653")
        painter.setPen(
            QPen(ink, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        )
        painter.setBrush(fur)
        if kind == "rabbit":
            painter.drawRoundedRect(QRectF(-72, -144, 44, 104), 22, 22)
            painter.drawRoundedRect(QRectF(28, -144, 44, 104), 22, 22)
        else:
            painter.drawPolygon(
                QPolygonF([QPointF(-95, -30), QPointF(-88, -113), QPointF(-28, -65)])
            )
            painter.drawPolygon(QPolygonF([QPointF(95, -30), QPointF(88, -113), QPointF(28, -65)]))
        painter.drawEllipse(QRectF(-77, 0, 154, 100))
        painter.drawEllipse(QRectF(-94, -83, 188, 148))
        painter.drawEllipse(QRectF(-76, 76, 54, 26))
        painter.drawEllipse(QRectF(22, 76, 54, 26))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#edb6bd"))
        painter.drawEllipse(QRectF(-70, -7, 28, 14))
        painter.drawEllipse(QRectF(42, -7, 28, 14))
        painter.setPen(QPen(ink, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        blink = index == count - 1
        for x in (-36, 36):
            if state in (Emotion.HAPPY, Emotion.SLEEPY) or blink:
                path = QPainterPath(QPointF(x - 10, -22))
                path.quadTo(x, -35 if state == Emotion.HAPPY else -16, x + 10, -22)
                painter.drawPath(path)
            else:
                painter.drawLine(QPointF(x, -29), QPointF(x, -16))
        if state == Emotion.ANGRY:
            painter.drawLine(QPointF(-49, -45), QPointF(-24, -35))
            painter.drawLine(QPointF(49, -45), QPointF(24, -35))
        mouth = QPainterPath(QPointF(-12, 14))
        mouth.quadTo(0, 3 if state == Emotion.ANGRY else 29, 12, 14)
        painter.drawPath(mouth)
    painter.end()
    return image
