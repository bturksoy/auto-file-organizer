"""Rules page: ordered list of RuleCard widgets with drag reorder."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QMessageBox, QScrollArea, QVBoxLayout, QWidget,
)

from app.core.state import AppState
from app.ui.dialogs.rule_edit import RuleEditDialog
from app.ui.pages.base_page import BasePage, InfoBanner
from app.ui.widgets.empty_state import EmptyState
from app.ui.widgets.rule_card import RuleCard


class RulesPage(BasePage):
    def __init__(self, state: AppState, parent=None) -> None:
        self._state = state
        super().__init__(
            title="Rules",
            subtitle="User-defined conditions and actions, evaluated in order.",
            action_label="+ New Rule",
            parent=parent,
        )
        if self.header.action_button:
            self.header.action_button.clicked.connect(self._add_new)

        state.profiles_changed.connect(self._refresh)
        state.active_profile_changed.connect(self._refresh)
        self._refresh()

    def build_body(self, layout: QVBoxLayout) -> None:
        layout.addWidget(InfoBanner(
            "Rules are checked in order from top to bottom. The first "
            "matching rule wins. Drag the ≡ handle to reorder priority."
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

    def _refresh(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        profile = self._state.active_profile()
        if not profile:
            return

        if not profile.rules:
            self._list_layout.addWidget(EmptyState(
                icon="⚡",
                title="No rules yet",
                message="Click + New Rule to define one. Rules run before "
                        "categories and can move, copy, or skip files based "
                        "on name, extension, size, age, or path.",
            ))
            self._list_layout.addStretch(1)
            return

        def lookup(category_id: str) -> str:
            for c in profile.categories:
                if c.id == category_id:
                    return c.name
            return ""

        for rule in profile.rules:
            card = RuleCard(rule, category_lookup=lookup)
            card.toggled.connect(self._on_toggled)
            card.edit_requested.connect(self._edit_existing)
            card.delete_requested.connect(self._delete_existing)
            card.drop_received.connect(self._on_reorder)
            self._list_layout.addWidget(card)
        self._list_layout.addStretch(1)

    def _on_toggled(self, rule_id: str, enabled: bool) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        for rule in profile.rules:
            if rule.id == rule_id:
                rule.enabled = enabled
                break
        self._state.save()

    def _add_new(self) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        dlg = RuleEditDialog(categories=profile.categories, parent=self)
        if dlg.exec():
            profile.rules.append(dlg.result_rule())
            self._state.save()
            self._refresh()

    def _edit_existing(self, rule_id: str) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        target = next((r for r in profile.rules if r.id == rule_id), None)
        if not target:
            return
        dlg = RuleEditDialog(rule=target, categories=profile.categories,
                             parent=self)
        if dlg.exec():
            self._state.save()
            self._refresh()

    def _delete_existing(self, rule_id: str) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        target = next((r for r in profile.rules if r.id == rule_id), None)
        if not target:
            return
        confirm = QMessageBox.question(
            self, "Delete rule",
            f"Remove the rule '{target.name}'?",
        )
        if confirm == QMessageBox.Yes:
            profile.rules = [r for r in profile.rules if r.id != rule_id]
            self._state.save()
            self._refresh()

    def _on_reorder(self, dropped_id: str, target_id: str) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        ids = [r.id for r in profile.rules]
        if dropped_id not in ids or target_id not in ids:
            return
        src_idx = ids.index(dropped_id)
        dst_idx = ids.index(target_id)
        dropped = profile.rules.pop(src_idx)
        # Insert before the drop target (intuitive)
        if dst_idx > src_idx:
            dst_idx -= 1
        profile.rules.insert(dst_idx, dropped)
        self._state.save()
        self._refresh()
