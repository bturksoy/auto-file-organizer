"""Small rounded label used for category extensions and similar pills."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class Chip(QLabel):
    def __init__(self, text: str, *, parent=None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "QLabel {"
            "  background-color: #1f2026;"
            "  color: #c5c9d4;"
            "  border: 1px solid #2c2e36;"
            "  border-radius: 10px;"
            "  padding: 3px 9px;"
            "  font-size: 11px;"
            "}"
        )
