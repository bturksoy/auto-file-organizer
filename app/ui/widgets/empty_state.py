"""Friendly placeholder shown when a list is empty."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class EmptyState(QWidget):
    def __init__(self, *, icon: str = "✦", title: str = "Nothing here yet",
                 message: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 36, 20, 36)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)

        glyph = QLabel(icon)
        glyph.setAlignment(Qt.AlignCenter)
        glyph.setStyleSheet("color: #4a4d56; font-size: 42px;")
        layout.addWidget(glyph)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(
            "color: #c5c9d4; font-size: 14px; font-weight: 600;")
        layout.addWidget(title_label)

        if message:
            msg = QLabel(message)
            msg.setAlignment(Qt.AlignCenter)
            msg.setWordWrap(True)
            msg.setStyleSheet("color: #9ba0ab;")
            layout.addWidget(msg)
