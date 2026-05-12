"""Categories page: live list of CategoryCard widgets, CRUD via dialogs."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QMessageBox, QScrollArea, QVBoxLayout, QWidget,
)

from app.core.state import AppState
from app.ui.dialogs.category_edit import CategoryEditDialog
from app.ui.pages.base_page import BasePage
from app.ui.widgets.category_card import CategoryCard


class CategoriesPage(BasePage):
    def __init__(self, state: AppState, parent=None) -> None:
        self._state = state
        super().__init__(
            title="Categories",
            subtitle="Extension-based groupings and their target folders.",
            action_label="+ New Category",
            parent=parent,
        )
        if self.header.action_button:
            self.header.action_button.clicked.connect(self._add_new)

        state.profiles_changed.connect(self._refresh)
        state.active_profile_changed.connect(self._refresh)
        self._refresh()

    def build_body(self, layout: QVBoxLayout) -> None:
        self._section_label = QLabel("DEFAULT CATEGORIES")
        self._section_label.setObjectName("sectionLabel")
        layout.addWidget(self._section_label)

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

    def _refresh(self) -> None:
        # Clear existing cards
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        profile = self._state.active_profile()
        if not profile:
            return
        for cat in profile.categories:
            card = CategoryCard(cat)
            card.toggled.connect(self._on_toggled)
            card.edit_requested.connect(self._edit_existing)
            card.delete_requested.connect(self._delete_existing)
            self._list_layout.addWidget(card)
        self._list_layout.addStretch(1)

    def _on_toggled(self, category_id: str, enabled: bool) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        for cat in profile.categories:
            if cat.id == category_id:
                cat.enabled = enabled
                break
        self._state.save()

    def _add_new(self) -> None:
        dlg = CategoryEditDialog(parent=self)
        if dlg.exec() == dlg.Accepted:
            profile = self._state.active_profile()
            if profile is None:
                return
            profile.categories.append(dlg.result_category())
            self._state.save()
            self._refresh()

    def _edit_existing(self, category_id: str) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        target = next((c for c in profile.categories if c.id == category_id),
                      None)
        if not target:
            return
        dlg = CategoryEditDialog(category=target, parent=self)
        if dlg.exec() == dlg.Accepted:
            self._state.save()
            self._refresh()

    def _delete_existing(self, category_id: str) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        target = next((c for c in profile.categories if c.id == category_id),
                      None)
        if not target or target.locked:
            return
        confirm = QMessageBox.question(
            self, "Delete category",
            f"Remove the '{target.name}' category? Files already in this "
            "category folder are not affected.",
        )
        if confirm == QMessageBox.Yes:
            profile.categories = [
                c for c in profile.categories if c.id != category_id
            ]
            self._state.save()
            self._refresh()
