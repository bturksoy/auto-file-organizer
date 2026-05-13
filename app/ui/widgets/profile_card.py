"""Card widget for a single Profile in the Profiles list."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMenu, QPushButton, QVBoxLayout,
)

from app.core.i18n import i18n
from app.core.models import Profile
from app.ui.icons import make_icon
from app.ui.theme import active_palette, palette_signal
from app.ui.widgets.card import Card
from app.ui.widgets.color_dot import ColorDot


class ProfileCard(Card):
    switch_requested = Signal(str)
    rename_requested = Signal(str)
    duplicate_requested = Signal(str)
    delete_requested = Signal(str)
    export_requested = Signal(str)

    def __init__(self, profile: Profile, *, is_active: bool, parent=None) -> None:
        super().__init__(parent)
        self._profile = profile

        row = QHBoxLayout()
        row.setSpacing(12)

        # Left column: name (+ optional badge) + meta line
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        # Color dot reflects the profile.color field — set when creating /
        # editing a profile, makes the list scannable at a glance.
        name_row.addWidget(ColorDot(profile.color, size=12))
        name = QLabel(profile.name or i18n.t("widget.profile_card.untitled"))
        name.setStyleSheet("font-size: 14px; font-weight: 600;")
        name_row.addWidget(name)
        if is_active:
            badge = QLabel(i18n.t("widget.profile_card.active"))
            badge.setObjectName("chipAccent")
            name_row.addWidget(badge)
        name_row.addStretch(1)
        text_col.addLayout(name_row)

        self._meta = QLabel(i18n.t(
            "widget.profile_card.meta",
            n=len(profile.rules), m=len(profile.categories),
        ))
        text_col.addWidget(self._meta)
        self._restyle()
        palette_signal().connect(self._restyle)

        row.addLayout(text_col, stretch=1)

        if is_active:
            disabled = QPushButton(i18n.t("widget.profile_card.active"))
            disabled.setObjectName("secondary")
            disabled.setEnabled(False)
            disabled.setFixedWidth(90)
            row.addWidget(disabled)
        else:
            switch_btn = QPushButton(i18n.t("widget.profile_card.switch_btn"))
            switch_btn.setObjectName("primary")
            switch_btn.setCursor(Qt.PointingHandCursor)
            switch_btn.setFixedWidth(90)
            switch_btn.clicked.connect(
                lambda: self.switch_requested.emit(self._profile.id))
            row.addWidget(switch_btn)

        self._menu_btn = QPushButton()
        self._menu_btn.setObjectName("iconBtn")
        self._menu_btn.setFixedSize(34, 30)
        self._menu_btn.setIconSize(QSize(16, 16))
        self._menu_btn.setCursor(Qt.PointingHandCursor)
        self._menu_btn.setToolTip(i18n.t("widget.profile_card.tooltip.menu"))
        self._menu_btn.clicked.connect(lambda: self._open_menu(self._menu_btn))
        row.addWidget(self._menu_btn)

        self.layout().addLayout(row)

    def _restyle(self) -> None:
        p = active_palette()
        self._meta.setStyleSheet(f"color: {p.text_dim}; font-size: 12px;")
        if hasattr(self, "_menu_btn"):
            self._menu_btn.setIcon(make_icon("dots", color=p.text_dim))

    def _open_menu(self, anchor: QPushButton) -> None:
        menu = QMenu(self)
        menu.addAction(i18n.t("action.rename"),
                       lambda: self.rename_requested.emit(self._profile.id))
        menu.addAction(i18n.t("action.duplicate"),
                       lambda: self.duplicate_requested.emit(self._profile.id))
        menu.addAction(i18n.t("action.export"),
                       lambda: self.export_requested.emit(self._profile.id))
        menu.addSeparator()
        menu.addAction(i18n.t("action.delete"),
                       lambda: self.delete_requested.emit(self._profile.id))
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomRight()))
