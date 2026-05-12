"""Friendly placeholder shown when a list is empty."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.ui.theme import active_palette, palette_signal


class EmptyState(QWidget):
    def __init__(self, *, icon: str = "✦", title: str = "Nothing here yet",
                 message: str = "", parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 36, 20, 36)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)

        self._glyph = QLabel(icon)
        self._glyph.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._glyph)

        self._title = QLabel(title)
        self._title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title)

        self._msg: QLabel | None = None
        if message:
            self._msg = QLabel(message)
            self._msg.setAlignment(Qt.AlignCenter)
            self._msg.setWordWrap(True)
            layout.addWidget(self._msg)

        self._refresh_style()
        palette_signal().connect(self._refresh_style)

    def _refresh_style(self) -> None:
        p = active_palette()
        self._glyph.setStyleSheet(f"color: {p.text_faint}; font-size: 42px;")
        self._title.setStyleSheet(
            f"color: {p.text}; font-size: 14px; font-weight: 600;")
        if self._msg:
            self._msg.setStyleSheet(f"color: {p.text_dim};")
