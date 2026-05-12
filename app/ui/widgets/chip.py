"""Small rounded label used for category extensions and similar pills."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ui.theme import active_palette, palette_signal


class Chip(QLabel):
    def __init__(self, text: str, *, parent=None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self._refresh_style()
        palette_signal().connect(self._refresh_style)

    def _refresh_style(self) -> None:
        p = active_palette()
        self.setStyleSheet(
            "QLabel {"
            f"  background-color: {p.bg_input};"
            f"  color: {p.text_dim};"
            f"  border: 1px solid {p.border};"
            "  border-radius: 10px;"
            "  padding: 3px 9px;"
            "  font-size: 11px;"
            "}"
        )

