"""Card widget for a single Rule. Up/Down arrow buttons reorder priority.

v2.7 replaced the drag handle (70 lines of mouse plumbing) with two arrow
buttons — discoverable, accessible, and a third of the code.
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QWidget,
)

from app.core.i18n import i18n
from app.core.models import (
    Action, Condition, CONDITION_LABELS, LEGACY_CONDITION_LABELS, Rule,
)
from app.ui.icons import make_icon
from app.ui.theme import active_palette, palette_signal
from app.ui.widgets.card import Card
from app.ui.widgets.toggle import Toggle


def _condition_label(condition_type: str) -> str:
    """Look up display text for both current and legacy condition types."""
    return (CONDITION_LABELS.get(condition_type)
            or LEGACY_CONDITION_LABELS.get(condition_type)
            or condition_type)


def describe_condition(c: Condition) -> str:
    return f"{_condition_label(c.type)} \"{c.value}\""


def describe_action(action: Action, *, is_copy: bool = False,
                    category_lookup=None) -> str:
    verb = "Copy" if is_copy else "Move"
    if action.type == "move_to_category":
        name = category_lookup(action.target) if category_lookup else None
        return f"→ {verb} to {name or action.target}"
    if action.type == "move_to_folder":
        return f"→ {verb} to {action.target or '...'}"
    return "→ (no action)"


class RuleCard(Card):
    edit_requested = Signal(str)
    delete_requested = Signal(str)
    toggled = Signal(str, bool)
    move_up_requested = Signal(str)
    move_down_requested = Signal(str)

    def __init__(self, rule: Rule, *, category_lookup=None,
                 match_count: int | None = None,
                 can_move_up: bool = True, can_move_down: bool = True,
                 parent=None) -> None:
        super().__init__(parent)
        self._rule = rule
        self._category_lookup = category_lookup

        header = QHBoxLayout()
        header.setSpacing(8)

        # Up/Down arrows live where the drag handle used to be.
        self._up_btn = self._mk_icon_button("Move up (higher priority)")
        self._up_btn.clicked.connect(
            lambda: self.move_up_requested.emit(self._rule.id))
        self._up_btn.setEnabled(can_move_up)
        header.addWidget(self._up_btn)

        self._down_btn = self._mk_icon_button("Move down (lower priority)")
        self._down_btn.clicked.connect(
            lambda: self.move_down_requested.emit(self._rule.id))
        self._down_btn.setEnabled(can_move_down)
        header.addWidget(self._down_btn)

        self.toggle = Toggle(checked=rule.enabled)
        self.toggle.toggled.connect(
            lambda v: self.toggled.emit(self._rule.id, v))
        header.addWidget(self.toggle)

        name_label = QLabel(rule.name or "(unnamed)")
        name_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        header.addWidget(name_label)

        header.addStretch(1)

        if match_count:
            badge_text = f"{match_count} {i18n.t('matches_label')}"
        else:
            badge_text = i18n.t("no_matches_label")
        chip = QLabel(badge_text)
        chip.setObjectName("chipNeutral" if not match_count else "chipAccent")
        header.addWidget(chip)

        self._edit_btn = self._mk_icon_button("Edit rule")
        self._edit_btn.clicked.connect(
            lambda: self.edit_requested.emit(self._rule.id))
        header.addWidget(self._edit_btn)

        self._del_btn = self._mk_icon_button("Delete rule")
        self._del_btn.clicked.connect(
            lambda: self.delete_requested.emit(self._rule.id))
        header.addWidget(self._del_btn)

        self.layout().addLayout(header)

        # Conditions summary — palette-aware so light mode stays readable.
        self._cond_labels: list[QLabel] = []
        for cond in rule.conditions:
            cond_label = QLabel(describe_condition(cond))
            self._cond_labels.append(cond_label)
            self.layout().addWidget(cond_label)

        self._action_label = QLabel(describe_action(
            rule.action, is_copy=rule.is_copy,
            category_lookup=category_lookup,
        ))
        self.layout().addWidget(self._action_label)
        self._restyle_text()
        palette_signal().connect(self._restyle_text)

    @staticmethod
    def _mk_icon_button(tooltip: str) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("iconBtn")
        btn.setFixedSize(30, 30)
        btn.setIconSize(QSize(16, 16))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(tooltip)
        return btn

    def _restyle_text(self) -> None:
        p = active_palette()
        for label in getattr(self, "_cond_labels", []):
            label.setStyleSheet(f"color: {p.text};")
        if hasattr(self, "_action_label"):
            self._action_label.setStyleSheet(
                f"color: {p.accent}; font-size: 13px; font-weight: 500;"
            )
        # Repaint icons in the new tint.
        if hasattr(self, "_up_btn"):
            self._up_btn.setIcon(make_icon("chevron_up", color=p.text_dim))
        if hasattr(self, "_down_btn"):
            self._down_btn.setIcon(make_icon("chevron_down", color=p.text_dim))
        if hasattr(self, "_edit_btn"):
            self._edit_btn.setIcon(make_icon("pencil", color=p.text_dim))
        if hasattr(self, "_del_btn"):
            self._del_btn.setIcon(make_icon("cross", color=p.text_dim))
