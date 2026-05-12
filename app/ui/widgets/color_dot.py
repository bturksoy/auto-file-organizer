"""Small colored circle used in category cards and similar lists."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget


class ColorDot(QWidget):
    def __init__(self, color: str = "#7c8cff", *, size: int = 10,
                 parent=None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self._size = size
        self.setFixedSize(size, size)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(0, 0, self._size, self._size)
