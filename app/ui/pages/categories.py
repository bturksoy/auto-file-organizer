"""Categories page: live list of CategoryCard widgets, CRUD via dialogs."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QMessageBox, QScrollArea, QVBoxLayout, QWidget,
)

from app.core.i18n import i18n
from app.core.state import AppState
from app.ui.dialogs.category_edit import CategoryEditDialog
from app.ui.pages.base_page import BasePage
from app.ui.widgets.category_card import CategoryCard


class CategoriesPage(BasePage):
    def __init__(self, state: AppState, parent=None) -> None:
        self._state = state
        super().__init__(
            title=i18n.t("page_categories_title"),
            subtitle=i18n.t("page_categories_subtitle"),
            action_label=i18n.t("new_category"),
            parent=parent,
        )
        if self.header.action_button:
            self.header.action_button.clicked.connect(self._add_new)

        state.profiles_changed.connect(self._refresh)
        state.active_profile_changed.connect(self._refresh)
        self._refresh()

    def build_body(self, layout: QVBoxLayout) -> None:
        self._section_label = QLabel(i18n.t("default_categories"))
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
        last_idx = len(profile.categories) - 1
        for idx, cat in enumerate(profile.categories):
            card = CategoryCard(
                cat,
                can_move_up=idx > 0,
                can_move_down=idx < last_idx,
            )
            card.toggled.connect(self._on_toggled)
            card.edit_requested.connect(self._edit_existing)
            card.delete_requested.connect(self._delete_existing)
            card.move_up_requested.connect(
                lambda cid: self._reorder(cid, -1))
            card.move_down_requested.connect(
                lambda cid: self._reorder(cid, +1))
            self._list_layout.addWidget(card)
        self._list_layout.addStretch(1)

    def _reorder(self, category_id: str, delta: int) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        ids = [c.id for c in profile.categories]
        if category_id not in ids:
            return
        idx = ids.index(category_id)
        new_idx = idx + delta
        if not 0 <= new_idx < len(profile.categories):
            return
        profile.categories[idx], profile.categories[new_idx] = (
            profile.categories[new_idx], profile.categories[idx])
        self._state.save()
        self._refresh()

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
        if dlg.exec():
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
        if dlg.exec():
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
            self, i18n.t("dialog.delete_category.title"),
            i18n.t("dialog.delete_category.body", name=target.name),
        )
        if confirm == QMessageBox.Yes:
            profile.categories = [
                c for c in profile.categories if c.id != category_id
            ]
            self._state.save()
            self._refresh()
