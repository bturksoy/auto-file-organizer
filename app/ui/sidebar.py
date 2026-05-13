"""Left navigation rail with vector icons."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QLabel, QPushButton, QSizePolicy, QSpacerItem,
    QVBoxLayout,
)

from app.core.i18n import i18n
from app.ui.icons import make_icon
from app.ui.theme import active_palette, palette_signal


# (key, label_i18n_key, icon)
NAV_ITEMS = [
    ("home",       "sidebar.home",       "home"),
    ("folders",    "sidebar.folders",    "folder"),
    ("rules",      "sidebar.rules",      "bolt"),
    ("categories", "sidebar.categories", "list"),
    ("profiles",   "sidebar.profiles",   "user"),
]

FOOTER_PAGE_ITEMS = [
    ("settings", "sidebar.settings", "gear"),
]

FOOTER_ACTION_ITEMS = [
    ("about", "sidebar.about", "info"),
]


class Sidebar(QFrame):
    """Vertical nav rail. Emits `selected(key)` when the user picks an item."""

    selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(210)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        self._icon_keys: dict[str, str] = {}
        self._build()
        palette_signal().connect(self._refresh_icons)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        title = QLabel(i18n.t("sidebar.app_title"))
        title.setObjectName("appTitle")
        layout.addWidget(title)

        for key, label_key, icon_key in NAV_ITEMS:
            btn = self._make_nav_button(
                key, i18n.t(label_key), icon_key, checkable=True)
            layout.addWidget(btn)

        layout.addItem(
            QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        for key, label_key, icon_key in FOOTER_PAGE_ITEMS:
            btn = self._make_nav_button(
                key, i18n.t(label_key), icon_key, checkable=True)
            layout.addWidget(btn)
        for key, label_key, icon_key in FOOTER_ACTION_ITEMS:
            btn = self._make_nav_button(
                key, i18n.t(label_key), icon_key, checkable=False)
            layout.addWidget(btn)

        layout.addSpacing(8)

    def _make_nav_button(self, key: str, label: str, icon_key: str,
                         *, checkable: bool) -> QPushButton:
        btn = QPushButton(f"  {label}")
        btn.setObjectName("navItem")
        btn.setCheckable(checkable)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setIconSize(QSize(18, 18))
        btn.clicked.connect(lambda _=False, k=key: self.selected.emit(k))
        if checkable:
            self._group.addButton(btn)
            self._buttons[key] = btn
        self._icon_keys[key] = icon_key
        btn._fo_key = key  # type: ignore[attr-defined]
        return btn

    def _refresh_icons(self) -> None:
        color = active_palette().text_dim
        for btn_key, icon_key in self._icon_keys.items():
            btn = self._buttons.get(btn_key)
            if btn is None:
                # Action item (not in checkable group). Walk children to find it.
                for child in self.findChildren(QPushButton):
                    if getattr(child, "_fo_key", None) == btn_key:
                        btn = child
                        break
            if btn is not None:
                btn.setIcon(make_icon(icon_key, size=18, color=color))

    def select(self, key: str) -> None:
        """Programmatic selection — used at startup."""
        btn = self._buttons.get(key)
        if btn:
            btn.setChecked(True)
            self.selected.emit(key)
            # First-time icon paint happens after the widget is parented.
            self._refresh_icons()
