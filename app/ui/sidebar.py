"""Left navigation rail."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QLabel, QPushButton, QSpacerItem, QSizePolicy,
    QVBoxLayout,
)


NAV_ITEMS = [
    ("home", "⌂  Home"),
    ("folders", "\U0001F4C1  Folders"),
    ("rules", "⚡  Rules"),
    ("categories", "☰  Categories"),
    ("profiles", "\U0001F464  Profiles"),
]

# Footer entries that do not switch pages (about, etc.). They emit
# the same `selected` signal so MainWindow can route them through a
# different handler.
FOOTER_PAGE_ITEMS = [
    ("settings", "⚙  Settings"),
]

FOOTER_ACTION_ITEMS = [
    ("about", "ⓘ  About"),
]

# Backwards-compat alias still consulted by older callers.
FOOTER_ITEMS = FOOTER_PAGE_ITEMS


class Sidebar(QFrame):
    """Vertical nav rail. Emits `selected(key)` when the user picks a page."""

    selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(210)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        title = QLabel("Auto File Organizer")
        title.setObjectName("appTitle")
        layout.addWidget(title)

        for key, label in NAV_ITEMS:
            btn = self._make_nav_button(key, label)
            layout.addWidget(btn)

        layout.addItem(
            QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        for key, label in FOOTER_PAGE_ITEMS:
            btn = self._make_nav_button(key, label)
            layout.addWidget(btn)
        for key, label in FOOTER_ACTION_ITEMS:
            btn = self._make_action_button(key, label)
            layout.addWidget(btn)

        layout.addSpacing(8)

    def _make_action_button(self, key: str, label: str) -> QPushButton:
        """Footer entry that fires `selected(key)` but isn't a checkable nav."""
        btn = QPushButton(label)
        btn.setObjectName("navItem")
        btn.setCheckable(False)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda _=False, k=key: self.selected.emit(k))
        return btn

    def _make_nav_button(self, key: str, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("navItem")
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda _=False, k=key: self._on_clicked(k))
        self._group.addButton(btn)
        self._buttons[key] = btn
        return btn

    def _on_clicked(self, key: str) -> None:
        self.selected.emit(key)

    def select(self, key: str) -> None:
        """Programmatic selection — used at startup."""
        btn = self._buttons.get(key)
        if btn:
            btn.setChecked(True)
            self.selected.emit(key)
