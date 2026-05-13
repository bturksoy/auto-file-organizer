"""Inline result banner shown on the Home page after an Organize run.

Replaces the always-auto-opening StatsDialog. The dialog still pops up
for big moves (>= STATS_THRESHOLD files) where the per-category
breakdown is genuinely useful; below that, the banner is enough.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)

from app.core.i18n import i18n
from app.ui.theme import active_palette, palette_signal


# When an organize run moves at least this many files we *also* open the
# full StatsDialog. Below the threshold the banner alone is enough.
STATS_THRESHOLD = 10


class OrganizeBanner(QFrame):
    """Compact result banner that lives directly under the progress bar."""

    stats_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("organizeBanner")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._kind = "success"

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 8, 8)
        row.setSpacing(10)

        self._glyph = QLabel("✓")
        self._glyph.setFixedWidth(20)
        self._glyph.setAlignment(Qt.AlignCenter)
        row.addWidget(self._glyph)

        self._text = QLabel("")
        self._text.setWordWrap(True)
        row.addWidget(self._text, stretch=1)

        self._stats_btn = QPushButton(i18n.t("widget.organize_banner.stats_btn"))
        self._stats_btn.setObjectName("secondary")
        self._stats_btn.setCursor(Qt.PointingHandCursor)
        self._stats_btn.clicked.connect(self.stats_requested.emit)
        row.addWidget(self._stats_btn)

        self._close_btn = QPushButton("×")
        self._close_btn.setObjectName("toastClose")
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.clicked.connect(self.hide)
        row.addWidget(self._close_btn)

        self.hide()
        self._restyle()
        palette_signal().connect(self._restyle)

    # ----- Public API ----------------------------------------------------

    def show_result(self, moved: int, errors: int, categories: int) -> None:
        """Render the result line, pick a tone, and reveal the banner."""
        if errors and not moved:
            self._kind = "error"
            self._glyph.setText("!")
            self._text.setText(i18n.t(
                "widget.organize_banner.errors_only", errors=errors))
            self._stats_btn.setVisible(False)
        elif moved == 0:
            self._kind = "info"
            self._glyph.setText("ⓘ")
            self._text.setText(i18n.t("widget.organize_banner.nothing"))
            self._stats_btn.setVisible(False)
        else:
            self._kind = "success"
            self._glyph.setText("✓")
            if errors:
                self._text.setText(i18n.t(
                    "widget.organize_banner.success_with_errors",
                    moved=moved, categories=categories, errors=errors))
            else:
                self._text.setText(i18n.t(
                    "widget.organize_banner.success",
                    moved=moved, categories=categories))
            self._stats_btn.setVisible(True)
        self._restyle()
        self.show()

    def hide_result(self) -> None:
        """Tucked away when a new organize starts."""
        self.hide()

    # ----- Styling -------------------------------------------------------

    def _restyle(self) -> None:
        p = active_palette()
        accent = {
            "success": p.success,
            "info":    p.accent,
            "error":   p.danger,
        }.get(self._kind, p.success)
        self.setStyleSheet(
            f"QFrame#organizeBanner {{"
            f" background-color: {p.bg_card}; border: 1px solid {p.border};"
            f" border-left: 3px solid {accent}; border-radius: 6px;"
            f"}}"
        )
        self._text.setStyleSheet(f"color: {p.text}; font-size: 13px;")
        self._glyph.setStyleSheet(
            f"color: {accent}; font-size: 16px; font-weight: 700;")
        self._close_btn.setStyleSheet(
            f"QPushButton#toastClose {{ color: {p.text_dim};"
            " background: transparent; border: none; font-size: 14px; }"
            f"QPushButton#toastClose:hover {{ color: {p.text}; }}"
        )
