"""Hand-drawn vector icons rendered through QPainter.

Why not bundle SVG files? Three reasons:
  * QIcon-from-svg requires bundling the files via PyInstaller --add-data
    and the QSvgRenderer module, which we already excluded for size.
  * SVG colors don't follow QSS, so we'd ship a separate set per theme.
  * The icons we need are small and geometric — straight lines, circles,
    a couple of rounded rectangles. QPainter does this in five lines.

Every icon takes a size and color and returns a QIcon. Callers should
recreate the QIcon when the theme switches so it picks up the new
accent / text color.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import (
    QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap,
)

from app.ui.theme import active_palette


_IconPainter = Callable[[QPainter, QSize, QColor], None]


def _pen(color: QColor, width: float = 1.6) -> QPen:
    pen = QPen(color)
    pen.setWidthF(width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


# ----- shape primitives --------------------------------------------------

def _home(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    pen = _pen(color, 1.7)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(w * 0.18, h * 0.50)
    path.lineTo(w * 0.50, h * 0.18)
    path.lineTo(w * 0.82, h * 0.50)
    path.lineTo(w * 0.82, h * 0.82)
    path.lineTo(w * 0.18, h * 0.82)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(int(w * 0.42), int(h * 0.82), int(w * 0.42), int(h * 0.60))
    p.drawLine(int(w * 0.58), int(h * 0.82), int(w * 0.58), int(h * 0.60))
    p.drawLine(int(w * 0.42), int(h * 0.60), int(w * 0.58), int(h * 0.60))


def _folder(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    p.setPen(_pen(color, 1.6))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(w * 0.16, h * 0.32)
    path.lineTo(w * 0.40, h * 0.32)
    path.lineTo(w * 0.48, h * 0.42)
    path.lineTo(w * 0.84, h * 0.42)
    path.lineTo(w * 0.84, h * 0.80)
    path.lineTo(w * 0.16, h * 0.80)
    path.closeSubpath()
    p.drawPath(path)


def _bolt(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    path = QPainterPath()
    path.moveTo(w * 0.54, h * 0.10)
    path.lineTo(w * 0.20, h * 0.56)
    path.lineTo(w * 0.46, h * 0.56)
    path.lineTo(w * 0.36, h * 0.90)
    path.lineTo(w * 0.78, h * 0.42)
    path.lineTo(w * 0.52, h * 0.42)
    path.closeSubpath()
    p.drawPath(path)


def _list(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    pen = _pen(color, 1.8)
    p.setPen(pen)
    for ratio in (0.30, 0.50, 0.70):
        y = int(h * ratio)
        p.drawLine(int(w * 0.20), y, int(w * 0.30), y)
        p.drawLine(int(w * 0.38), y, int(w * 0.82), y)


def _user(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    p.setPen(_pen(color, 1.6))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(int(w * 0.34), int(h * 0.16),
                  int(w * 0.32), int(h * 0.32))
    path = QPainterPath()
    path.moveTo(w * 0.16, h * 0.86)
    path.cubicTo(w * 0.20, h * 0.56, w * 0.80, h * 0.56, w * 0.84, h * 0.86)
    p.drawPath(path)


def _gear(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    p.setPen(_pen(color, 1.6))
    p.setBrush(Qt.NoBrush)
    cx, cy = w / 2.0, h / 2.0
    p.drawEllipse(int(w * 0.38), int(h * 0.38),
                  int(w * 0.24), int(h * 0.24))
    # eight tick marks around the gear
    from math import cos, sin, radians
    r1 = w * 0.30
    r2 = w * 0.42
    for k in range(8):
        ang = radians(k * 45)
        x1 = cx + r1 * cos(ang)
        y1 = cy + r1 * sin(ang)
        x2 = cx + r2 * cos(ang)
        y2 = cy + r2 * sin(ang)
        p.drawLine(int(x1), int(y1), int(x2), int(y2))


def _info(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    p.setPen(_pen(color, 1.6))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(int(w * 0.18), int(h * 0.18),
                  int(w * 0.64), int(h * 0.64))
    p.setPen(_pen(color, 1.8))
    p.drawLine(int(w * 0.50), int(h * 0.40), int(w * 0.50), int(h * 0.40))
    p.drawLine(int(w * 0.50), int(h * 0.50), int(w * 0.50), int(h * 0.72))


def _pencil(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    p.setPen(_pen(color, 1.6))
    p.setBrush(Qt.NoBrush)
    p.drawLine(int(w * 0.22), int(h * 0.78),
               int(w * 0.78), int(h * 0.22))
    p.drawLine(int(w * 0.22), int(h * 0.78),
               int(w * 0.30), int(h * 0.86))
    p.drawLine(int(w * 0.62), int(h * 0.20),
               int(w * 0.80), int(h * 0.38))


def _cross(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    p.setPen(_pen(color, 1.8))
    p.drawLine(int(w * 0.26), int(h * 0.26),
               int(w * 0.74), int(h * 0.74))
    p.drawLine(int(w * 0.26), int(h * 0.74),
               int(w * 0.74), int(h * 0.26))


def _dots(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    r = w * 0.08
    cy = h * 0.50
    for cx in (w * 0.28, w * 0.50, w * 0.72):
        p.drawEllipse(QPoint(int(cx), int(cy)), int(r), int(r))


def _grip(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    p.setPen(_pen(color, 1.8))
    for ratio in (0.30, 0.50, 0.70):
        y = int(h * ratio)
        p.drawLine(int(w * 0.28), y, int(w * 0.72), y)


def _lock(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    p.setPen(_pen(color, 1.6))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(int(w * 0.26), int(h * 0.46),
                      int(w * 0.48), int(h * 0.36), 3, 3)
    path = QPainterPath()
    path.moveTo(w * 0.36, h * 0.46)
    path.lineTo(w * 0.36, h * 0.34)
    path.cubicTo(w * 0.36, h * 0.18, w * 0.64, h * 0.18, w * 0.64, h * 0.34)
    path.lineTo(w * 0.64, h * 0.46)
    p.drawPath(path)


def _sun(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    p.setPen(_pen(color, 1.6))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(int(w * 0.34), int(h * 0.34),
                  int(w * 0.32), int(h * 0.32))
    from math import cos, sin, radians
    cx, cy = w / 2.0, h / 2.0
    r1 = w * 0.40
    r2 = w * 0.46
    for k in range(8):
        ang = radians(k * 45)
        p.drawLine(int(cx + r1 * cos(ang)), int(cy + r1 * sin(ang)),
                   int(cx + r2 * cos(ang)), int(cy + r2 * sin(ang)))


def _moon(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawEllipse(int(w * 0.22), int(h * 0.18),
                  int(w * 0.56), int(h * 0.56))
    bg = active_palette().bg_app
    p.setBrush(QColor(bg))
    p.drawEllipse(int(w * 0.34), int(h * 0.16),
                  int(w * 0.52), int(h * 0.52))


def _plus(p: QPainter, size: QSize, color: QColor) -> None:
    w, h = size.width(), size.height()
    p.setPen(_pen(color, 1.8))
    p.drawLine(int(w * 0.30), int(h * 0.50),
               int(w * 0.70), int(h * 0.50))
    p.drawLine(int(w * 0.50), int(h * 0.30),
               int(w * 0.50), int(h * 0.70))


_PAINTERS: dict[str, _IconPainter] = {
    "home": _home,
    "folder": _folder,
    "bolt": _bolt,
    "list": _list,
    "user": _user,
    "gear": _gear,
    "info": _info,
    "pencil": _pencil,
    "cross": _cross,
    "dots": _dots,
    "grip": _grip,
    "lock": _lock,
    "sun": _sun,
    "moon": _moon,
    "plus": _plus,
}


def make_icon(name: str, *, size: int = 18,
              color: QColor | str | None = None) -> QIcon:
    """Return a QIcon for the named glyph in the requested color."""
    painter = _PAINTERS.get(name)
    if painter is None:
        return QIcon()
    if isinstance(color, str):
        color = QColor(color)
    if color is None:
        color = QColor(active_palette().text_dim)
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)
    painter(p, QSize(size, size), color)
    p.end()
    return QIcon(pix)


def make_pixmap(name: str, *, size: int = 18,
                color: QColor | str | None = None) -> QPixmap:
    """Same as make_icon but returns a raw QPixmap for QLabel.setPixmap."""
    return make_icon(name, size=size, color=color).pixmap(size, size)
