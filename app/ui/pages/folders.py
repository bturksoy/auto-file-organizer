"""Folders page: recent + destination + watched."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from app.core.i18n import i18n
from app.core.state import AppState
from app.ui.pages.base_page import BasePage, InfoBanner
from app.ui.widgets.card import Card


class FoldersPage(BasePage):
    def __init__(self, state: AppState, parent=None) -> None:
        self._state = state
        super().__init__(
            title=i18n.t("page_folders_title"),
            subtitle=i18n.t("page_folders_subtitle"),
            parent=parent,
        )
        state.profiles_changed.connect(self._refresh_paths)
        state.active_profile_changed.connect(self._refresh_paths)
        state.folder_changed.connect(lambda _: self._refresh_recent())
        self._refresh_paths()
        self._refresh_recent()

    def build_body(self, layout: QVBoxLayout) -> None:
        layout.addWidget(InfoBanner(i18n.t("page_folders_banner")))

        layout.addWidget(self._build_destination_card())
        layout.addWidget(self._build_watched_card())
        layout.addWidget(self._build_recent_card(), stretch=1)

    # ----- destination -----

    def _build_destination_card(self) -> Card:
        card = Card()
        card.layout().addWidget(self._h2("Destination folder"))
        body = QHBoxLayout()
        self._dest_edit = QLineEdit()
        self._dest_edit.setPlaceholderText("Leave empty to organize in place")
        self._dest_edit.editingFinished.connect(self._save_dest)
        body.addWidget(self._dest_edit, stretch=1)
        browse = QPushButton("Browse...")
        browse.setObjectName("secondary")
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(self._pick_destination)
        body.addWidget(browse)
        clear = QPushButton("Clear")
        clear.setObjectName("secondary")
        clear.setCursor(Qt.PointingHandCursor)
        clear.clicked.connect(lambda: (self._dest_edit.setText(""),
                                       self._save_dest()))
        body.addWidget(clear)
        card.layout().addLayout(body)
        return card

    # ----- watched -----

    def _build_watched_card(self) -> Card:
        card = Card()
        card.layout().addWidget(self._h2("Watched folders (background mode)"))
        hint = QLabel(
            "Each folder listed here is scanned on the auto-organize "
            "schedule. Add as many as you like — Downloads, Desktop, "
            "Pictures, anything that fills up."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9ba0ab;")
        card.layout().addWidget(hint)

        self._watch_list = QListWidget()
        self._watch_list.setStyleSheet(
            "QListWidget { background: transparent; border: none; }"
            " QListWidget::item { padding: 6px 4px; }"
        )
        card.layout().addWidget(self._watch_list)

        row = QHBoxLayout()
        add = QPushButton("+ Add folder")
        add.setObjectName("secondary")
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(self._add_watched)
        row.addWidget(add)
        remove = QPushButton("Remove selected")
        remove.setObjectName("secondary")
        remove.setCursor(Qt.PointingHandCursor)
        remove.clicked.connect(self._remove_watched)
        row.addWidget(remove)
        row.addStretch(1)
        card.layout().addLayout(row)
        return card

    # ----- recent -----

    def _build_recent_card(self) -> Card:
        card = Card()
        card.layout().addWidget(self._h2("Recent folders"))
        self._recent_list = QListWidget()
        self._recent_list.setStyleSheet(
            "QListWidget { background: transparent; border: none; }"
            " QListWidget::item { padding: 6px 4px; }"
            " QListWidget::item:hover { background: #2a2c34; border-radius: 6px; }"
        )
        self._recent_list.itemDoubleClicked.connect(self._open_recent)
        card.layout().addWidget(self._recent_list)
        return card

    @staticmethod
    def _h2(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-size: 14px; font-weight: 600;")
        return label

    # ----- handlers -----

    def _refresh_paths(self) -> None:
        profile = self._state.active_profile()
        if not profile:
            self._dest_edit.setText("")
            self._watch_list.clear()
            return
        self._dest_edit.setText(profile.settings.destination_folder)
        self._watch_list.clear()
        for folder in profile.settings.watched_folders:
            item = QListWidgetItem(folder)
            self._watch_list.addItem(item)

    def _refresh_recent(self) -> None:
        self._recent_list.clear()
        for folder in self._state.data.recent_folders:
            item = QListWidgetItem(folder)
            item.setData(Qt.UserRole, folder)
            self._recent_list.addItem(item)

    def _pick_destination(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select destination")
        if folder:
            self._dest_edit.setText(folder)
            self._save_dest()

    def _save_dest(self) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        profile.settings.destination_folder = self._dest_edit.text().strip()
        self._state.save()

    def _add_watched(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add watched folder")
        if not folder:
            return
        profile = self._state.active_profile()
        if not profile:
            return
        if folder in profile.settings.watched_folders:
            return
        profile.settings.watched_folders.append(folder)
        # Keep legacy single-folder field in sync with the first entry so
        # older builds reading the same appdata.json still see something.
        if not profile.settings.watched_folder:
            profile.settings.watched_folder = folder
        self._state.save()
        self._refresh_paths()

    def _remove_watched(self) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        selected = self._watch_list.selectedItems()
        if not selected:
            return
        keep = []
        removed = {item.text() for item in selected}
        for folder in profile.settings.watched_folders:
            if folder not in removed:
                keep.append(folder)
        profile.settings.watched_folders = keep
        if profile.settings.watched_folder in removed:
            profile.settings.watched_folder = keep[0] if keep else ""
        self._state.save()
        self._refresh_paths()

    def _open_recent(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if not path:
            return
        p = Path(path)
        if p.is_dir():
            self._state.set_folder(p)
