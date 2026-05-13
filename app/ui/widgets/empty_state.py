"""Friendly placeholder shown when a list is empty.

Pages pass `action_label` + `action_callback` when they want the empty
state to also offer a one-click way to create the first entry — this is
the empty-state CTA pattern.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.i18n import i18n
from app.ui.theme import active_palette, palette_signal


class EmptyState(QWidget):
    def __init__(self, *, icon: str = "✦", title: str | None = None,
                 message: str = "",
                 action_label: str | None = None,
                 action_callback: Callable[[], None] | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        if title is None:
            title = i18n.t("widget.empty_state.default_title")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 36, 20, 36)
        layout.setSpacing(8)
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

        self._action_btn: QPushButton | None = None
        if action_label and action_callback is not None:
            self._action_btn = QPushButton(action_label)
            self._action_btn.setObjectName("primary")
            self._action_btn.setCursor(Qt.PointingHandCursor)
            self._action_btn.clicked.connect(action_callback)
            layout.addWidget(self._action_btn, alignment=Qt.AlignCenter)

        self._refresh_style()
        palette_signal().connect(self._refresh_style)

    def _refresh_style(self) -> None:
        p = active_palette()
        self._glyph.setStyleSheet(f"color: {p.text_faint}; font-size: 42px;")
        self._title.setStyleSheet(
            f"color: {p.text}; font-size: 14px; font-weight: 600;")
        if self._msg:
            self._msg.setStyleSheet(f"color: {p.text_dim};")
