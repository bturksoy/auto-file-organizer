"""Rounded card container for list items."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout


class Card(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        # Cards must not be squished by their parent layout — they should
        # demand at least their content size and grow horizontally only.
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(10)

    def layout(self) -> QVBoxLayout:  # type: ignore[override]
        return self._layout
