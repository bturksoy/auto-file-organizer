"""Rules page: ordered list of RuleCard widgets with drag reorder."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QMessageBox, QScrollArea, QVBoxLayout, QWidget,
)

from app.core.i18n import i18n
from app.core.match_counts import count_matches
from app.core.state import AppState
from app.ui.dialogs.rule_edit import RuleEditDialog
from app.ui.pages.base_page import BasePage, InfoBanner
from app.ui.widgets.empty_state import EmptyState
from app.ui.widgets.rule_card import RuleCard


class _CountsBridge(QObject):
    counts_ready = Signal(dict)


class RulesPage(BasePage):
    def __init__(self, state: AppState, parent=None) -> None:
        self._state = state
        self._counts: dict[str, int] = {}
        self._counts_bridge = _CountsBridge()
        self._counts_bridge.counts_ready.connect(self._on_counts_ready)
        super().__init__(
            title=i18n.t("page_rules_title"),
            subtitle=i18n.t("page_rules_subtitle"),
            action_label=i18n.t("new_rule"),
            parent=parent,
        )
        if self.header.action_button:
            self.header.action_button.clicked.connect(self._add_new)

        state.profiles_changed.connect(self._on_data_changed)
        state.active_profile_changed.connect(self._on_data_changed)
        state.folder_changed.connect(lambda _: self._spawn_count_scan())
        self._refresh()

    def _on_data_changed(self) -> None:
        self._refresh()
        self._spawn_count_scan()

    def _spawn_count_scan(self) -> None:
        folder = self._state.current_folder
        profile = self._state.active_profile()
        if folder is None or profile is None:
            self._counts = {}
            self._refresh()
            return

        def work():
            try:
                counts = count_matches(folder, profile)
            except Exception:
                counts = {}
            self._counts_bridge.counts_ready.emit(counts)
        threading.Thread(target=work, daemon=True).start()

    def _on_counts_ready(self, counts: dict) -> None:
        self._counts = counts
        self._refresh()

    def build_body(self, layout: QVBoxLayout) -> None:
        layout.addWidget(InfoBanner(i18n.t("page.rules.banner")))

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
                title=i18n.t("no_rules_yet"),
                message=i18n.t("no_rules_hint"),
                action_label=i18n.t("new_rule"),
                action_callback=self._add_new,
            ))
            self._list_layout.addStretch(1)
            return

        def lookup(category_id: str) -> str:
            for c in profile.categories:
                if c.id == category_id:
                    return c.name
            return ""

        last_idx = len(profile.rules) - 1
        for idx, rule in enumerate(profile.rules):
            card = RuleCard(
                rule, category_lookup=lookup,
                match_count=self._counts.get(rule.id, 0),
                can_move_up=idx > 0,
                can_move_down=idx < last_idx,
            )
            card.toggled.connect(self._on_toggled)
            card.edit_requested.connect(self._edit_existing)
            card.delete_requested.connect(self._delete_existing)
            card.move_up_requested.connect(
                lambda rid: self._reorder(rid, -1))
            card.move_down_requested.connect(
                lambda rid: self._reorder(rid, +1))
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
        dlg = RuleEditDialog(
            categories=profile.categories,
            profile=profile,
            test_folder=self._state.current_folder,
            parent=self,
        )
        if dlg.exec():
            profile.rules.append(dlg.result_rule())
            self._state.save()
            self._refresh()
            self._spawn_count_scan()

    def _edit_existing(self, rule_id: str) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        target = next((r for r in profile.rules if r.id == rule_id), None)
        if not target:
            return
        dlg = RuleEditDialog(
            rule=target, categories=profile.categories,
            profile=profile,
            test_folder=self._state.current_folder,
            parent=self,
        )
        if dlg.exec():
            self._state.save()
            self._refresh()
            self._spawn_count_scan()

    def _delete_existing(self, rule_id: str) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        target = next((r for r in profile.rules if r.id == rule_id), None)
        if not target:
            return
        confirm = QMessageBox.question(
            self, i18n.t("dialog.delete_rule.title"),
            i18n.t("dialog.delete_rule.body", name=target.name),
        )
        if confirm == QMessageBox.Yes:
            profile.rules = [r for r in profile.rules if r.id != rule_id]
            self._state.save()
            self._refresh()

    def _reorder(self, rule_id: str, delta: int) -> None:
        """Swap the rule with its neighbour in the direction of `delta`."""
        profile = self._state.active_profile()
        if not profile:
            return
        ids = [r.id for r in profile.rules]
        if rule_id not in ids:
            return
        idx = ids.index(rule_id)
        new_idx = idx + delta
        if not 0 <= new_idx < len(profile.rules):
            return
        profile.rules[idx], profile.rules[new_idx] = (
            profile.rules[new_idx], profile.rules[idx])
        self._state.save()
        self._refresh()
