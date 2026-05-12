"""Shared layout primitives for every page in the app."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)


class PageHeader(QWidget):
    """Page title + optional subtitle row, with an optional primary action."""

    def __init__(self, title: str, subtitle: str = "",
                 action_label: str | None = None, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        left = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        left.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("pageSubtitle")
            left.addWidget(subtitle_label)
        layout.addLayout(left)

        layout.addStretch(1)

        self.action_button: QPushButton | None = None
        if action_label:
            self.action_button = QPushButton(action_label)
            self.action_button.setObjectName("primary")
            self.action_button.setCursor(Qt.PointingHandCursor)
            layout.addWidget(self.action_button, alignment=Qt.AlignTop)


class InfoBanner(QFrame):
    """Soft accent-colored note that explains how the current page works."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("infoBanner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        label = QLabel(text)
        label.setObjectName("infoBannerText")
        label.setWordWrap(True)
        layout.addWidget(label)


class BasePage(QWidget):
    """Vertical scroll-able page with a header row.

    Subclasses override `build_body(layout)` and add their content. The
    last widget they add SHOULD claim the remaining space (stretch=1) —
    typically a QScrollArea or a content area. The page does not add a
    trailing stretch on its own; the child decides where slack goes.
    """

    def __init__(self, title: str, subtitle: str = "",
                 action_label: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("pageRoot")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(16)

        self.header = PageHeader(title, subtitle, action_label)
        layout.addWidget(self.header)

        self._content_layout = layout
        self.build_body(layout)

    def build_body(self, layout: QVBoxLayout) -> None:
        """Override in subclasses to add page-specific widgets."""
