"""Profiles page: list of named configurations, switching + import/export."""
from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from app.core.models import Profile
from app.core.state import AppState
from app.ui.dialogs.profile_edit import ProfileNameDialog
from app.ui.pages.base_page import BasePage, InfoBanner
from app.ui.widgets.profile_card import ProfileCard


class ProfilesPage(BasePage):
    def __init__(self, state: AppState, parent=None) -> None:
        self._state = state
        super().__init__(
            title="Profiles",
            subtitle="Save and switch between different organization configurations.",
            action_label="+ New Profile",
            parent=parent,
        )
        if self.header.action_button:
            self.header.action_button.clicked.connect(self._add_new)

        state.profiles_changed.connect(self._refresh)
        state.active_profile_changed.connect(self._refresh)
        self._refresh()

    def build_body(self, layout: QVBoxLayout) -> None:
        # Extra "Import" button next to the page action.
        if self.header.action_button:
            import_btn = QPushButton("→ Import")
            import_btn.setObjectName("secondary")
            import_btn.setCursor(Qt.PointingHandCursor)
            import_btn.clicked.connect(self._import_profile)
            self.header.layout().insertWidget(
                self.header.layout().count() - 1, import_btn)

        layout.addWidget(InfoBanner(
            "Each profile contains its own rules, categories, and settings. "
            "Switch profiles to use different organization configurations for "
            "different purposes."
        ))

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        layout.addWidget(self._scroll, stretch=1)

        holder = QWidget()
        self._list_layout = QVBoxLayout(holder)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(10)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(holder)

    # ----- list rendering -----

    def _refresh(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        active_id = self._state.data.active_profile_id
        for profile in self._state.data.profiles:
            card = ProfileCard(profile, is_active=(profile.id == active_id))
            card.switch_requested.connect(self._state.set_active_profile)
            card.rename_requested.connect(self._rename)
            card.duplicate_requested.connect(self._duplicate)
            card.delete_requested.connect(self._delete)
            card.export_requested.connect(self._export)
            self._list_layout.addWidget(card)
        self._list_layout.addStretch(1)

    # ----- actions -----

    def _add_new(self) -> None:
        dlg = ProfileNameDialog(title="New profile", parent=self)
        if dlg.exec() != dlg.Accepted:
            return
        # Seed an empty profile (no rules, no categories) unless you'd prefer
        # to clone the active one. Cloning is friendlier for first-time users.
        active = self._state.active_profile()
        seed_categories = (
            [copy.deepcopy(c) for c in active.categories] if active else [])
        profile = Profile(
            id=uuid.uuid4().hex,
            name=dlg.value(),
            rules=[],
            categories=seed_categories,
        )
        self._state.add_profile(profile)

    def _rename(self, profile_id: str) -> None:
        target = self._find(profile_id)
        if not target:
            return
        dlg = ProfileNameDialog(
            title="Rename profile", initial=target.name, parent=self)
        if dlg.exec() == dlg.Accepted:
            target.name = dlg.value()
            self._state.save()
            self._refresh()

    def _duplicate(self, profile_id: str) -> None:
        target = self._find(profile_id)
        if not target:
            return
        clone = copy.deepcopy(target)
        clone.id = uuid.uuid4().hex
        clone.name = f"{target.name} (copy)"
        self._state.add_profile(clone)

    def _delete(self, profile_id: str) -> None:
        target = self._find(profile_id)
        if not target:
            return
        if len(self._state.data.profiles) <= 1:
            QMessageBox.information(
                self, "Cannot delete",
                "At least one profile must exist.",
            )
            return
        confirm = QMessageBox.question(
            self, "Delete profile",
            f"Remove the profile '{target.name}'? Files already on disk "
            "are not touched.",
        )
        if confirm == QMessageBox.Yes:
            self._state.remove_profile(profile_id)

    def _export(self, profile_id: str) -> None:
        target = self._find(profile_id)
        if not target:
            return
        suggested = f"{target.name}.profile.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export profile", suggested, "Profile JSON (*.json)")
        if not path:
            return
        try:
            Path(path).write_text(
                json.dumps(target.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def _import_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import profile", "", "Profile JSON (*.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            imported = Profile.from_dict(data)
            imported.id = uuid.uuid4().hex
            self._state.add_profile(imported)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Import failed", str(exc))

    def _find(self, profile_id: str) -> Profile | None:
        for p in self._state.data.profiles:
            if p.id == profile_id:
                return p
        return None
