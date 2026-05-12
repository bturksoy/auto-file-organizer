"""Card widget for a single Profile in the Profiles list."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMenu, QPushButton, QVBoxLayout,
)

from app.core.models import Profile
from app.ui.theme import active_palette, palette_signal
from app.ui.widgets.card import Card


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
        name = QLabel(profile.name or "Untitled")
        name.setStyleSheet("font-size: 14px; font-weight: 600;")
        name_row.addWidget(name)
        if is_active:
            badge = QLabel("Active")
            badge.setObjectName("chipAccent")
            name_row.addWidget(badge)
        name_row.addStretch(1)
        text_col.addLayout(name_row)

        self._meta = QLabel(
            f"{len(profile.rules)} rules · {len(profile.categories)} categories"
        )
        text_col.addWidget(self._meta)
        self._restyle()
        palette_signal().connect(self._restyle)

        row.addLayout(text_col, stretch=1)

        if is_active:
            disabled = QPushButton("Active")
            disabled.setObjectName("secondary")
            disabled.setEnabled(False)
            disabled.setFixedWidth(90)
            row.addWidget(disabled)
        else:
            switch_btn = QPushButton("Switch")
            switch_btn.setObjectName("primary")
            switch_btn.setCursor(Qt.PointingHandCursor)
            switch_btn.setFixedWidth(90)
            switch_btn.clicked.connect(
                lambda: self.switch_requested.emit(self._profile.id))
            row.addWidget(switch_btn)

        menu_btn = QPushButton("⋯")
        menu_btn.setObjectName("iconBtn")
        menu_btn.setFixedSize(34, 30)
        menu_btn.setCursor(Qt.PointingHandCursor)
        menu_btn.setToolTip("Profile actions")
        menu_btn.clicked.connect(lambda: self._open_menu(menu_btn))
        row.addWidget(menu_btn)

        self.layout().addLayout(row)

    def _restyle(self) -> None:
        p = active_palette()
        self._meta.setStyleSheet(f"color: {p.text_dim}; font-size: 12px;")

    def _open_menu(self, anchor: QPushButton) -> None:
        menu = QMenu(self)
        menu.addAction("Rename",
                       lambda: self.rename_requested.emit(self._profile.id))
        menu.addAction("Duplicate",
                       lambda: self.duplicate_requested.emit(self._profile.id))
        menu.addAction("Export…",
                       lambda: self.export_requested.emit(self._profile.id))
        menu.addSeparator()
        menu.addAction("Delete",
                       lambda: self.delete_requested.emit(self._profile.id))
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomRight()))
