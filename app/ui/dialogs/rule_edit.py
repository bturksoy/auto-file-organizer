"""Modal dialog to create or edit a Rule (conditions + action).

v2.7 removed the in-dialog Test feature — the Rules page shows live match
counts per rule already (faster + accurate). v2.7 also dropped 4 obscure
condition types and the skip / copy_to_* action variants. Copy-vs-move
is now a checkbox on the rule itself.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from app.core.models import (
    ACTION_TYPES, CONDITION_LABELS, CONDITION_TYPES, Action, Category,
    Condition, ConditionGroup, Profile, Rule,
)


_CONDITION_HELP = {
    "name_contains": "substring",
    "name_starts_with": "prefix",
    "name_ends_with": "suffix",
    "name_regex": "regex pattern",
    "extension_in": ".jpg, .png, .webp",
    "path_contains": "subfolder name in source path",
    "size_above_mb": "10",
    "size_below_mb": "10",
    "age_above_days": "30  (older than)",
    "age_below_days": "30  (newer than)",
    "content_matches": "Pick a pattern (manage from Settings)",
}

_ACTION_LABELS = {
    "move_to_category": "Send to category",
    "move_to_folder":   "Send to folder",
}


class _ConditionRow(QWidget):
    def __init__(self, condition: Condition | None = None,
                 profile: Profile | None = None, parent=None) -> None:
        super().__init__(parent)
        self._profile = profile
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.type_combo = QComboBox()
        for ct in CONDITION_TYPES:
            self.type_combo.addItem(CONDITION_LABELS[ct], userData=ct)
        # Legacy condition types from v2.6 profiles still load — show them
        # in the dropdown for the existing row so users can edit but not
        # create new ones.
        if condition and condition.type not in CONDITION_TYPES:
            from app.core.models import LEGACY_CONDITION_LABELS
            label = LEGACY_CONDITION_LABELS.get(
                condition.type, condition.type)
            self.type_combo.addItem(f"[legacy] {label}",
                                    userData=condition.type)

        if condition:
            idx = self.type_combo.findData(condition.type)
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self.type_combo, stretch=1)

        # Two value widgets — one freeform, one pattern picker. Visibility
        # toggles based on the condition type.
        self.value_edit = QLineEdit(condition.value if condition else "")
        layout.addWidget(self.value_edit, stretch=2)

        self.pattern_combo = QComboBox()
        if profile is not None:
            for pattern in profile.content_patterns:
                self.pattern_combo.addItem(pattern.name, userData=pattern.id)
        if condition and condition.type == "content_matches":
            for i in range(self.pattern_combo.count()):
                if self.pattern_combo.itemData(i) == condition.value:
                    self.pattern_combo.setCurrentIndex(i)
                    break
        layout.addWidget(self.pattern_combo, stretch=2)

        self.remove_btn = QPushButton("×")
        self.remove_btn.setObjectName("secondary")
        self.remove_btn.setFixedSize(28, 28)
        self.remove_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.remove_btn)

        self._on_type_changed()

    def _on_type_changed(self) -> None:
        ct = self.type_combo.currentData()
        self.value_edit.setPlaceholderText(_CONDITION_HELP.get(ct, ""))
        is_pattern = ct == "content_matches"
        self.value_edit.setVisible(not is_pattern)
        self.pattern_combo.setVisible(is_pattern)

    def to_condition(self) -> Condition:
        ct = self.type_combo.currentData()
        if ct == "content_matches":
            value = self.pattern_combo.currentData() or ""
        else:
            value = self.value_edit.text().strip()
        return Condition(type=ct, value=value)


class RuleEditDialog(QDialog):
    """Edit a rule's name, conditions, and action.

    The dialog returns a `Rule` from `result_rule()` *only after* the user
    clicks Save. Cancel leaves the original untouched.
    """

    def __init__(self, *, rule: Rule | None = None,
                 categories: list[Category],
                 profile: Profile | None = None,
                 test_folder: Path | None = None,  # kept for API compat
                 parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit rule" if rule else "New rule")
        self.setMinimumWidth(580)

        self._original = rule
        self._categories = categories
        self._profile = profile

        outer = QVBoxLayout(self)
        form = QFormLayout()
        outer.addLayout(form)

        self.name_edit = QLineEdit(rule.name if rule else "")
        self.name_edit.setPlaceholderText("e.g. Old invoices")
        form.addRow("Rule name", self.name_edit)

        op_row = QHBoxLayout()
        op_row.addWidget(self._section_label("Conditions"))
        op_row.addStretch(1)
        op_row.addWidget(QLabel("Match:"))
        self.operator_combo = QComboBox()
        self.operator_combo.addItem("All (AND)", userData="and")
        self.operator_combo.addItem("Any (OR)", userData="or")
        if rule and rule.condition_root and rule.condition_root.operator == "or":
            self.operator_combo.setCurrentIndex(1)
        op_row.addWidget(self.operator_combo)
        outer.addLayout(op_row)

        self._conditions_holder = QFrame()
        self._conditions_layout = QVBoxLayout(self._conditions_holder)
        self._conditions_layout.setContentsMargins(0, 0, 0, 0)
        self._conditions_layout.setSpacing(6)
        outer.addWidget(self._conditions_holder)

        add_btn = QPushButton("+ Add condition")
        add_btn.setObjectName("secondary")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(lambda: self._add_condition_row())
        outer.addWidget(add_btn, alignment=Qt.AlignLeft)

        # Seed with the rule's existing conditions (flatten the tree if set).
        seed: list[Condition] = []
        if rule:
            if rule.condition_root:
                def collect(group: ConditionGroup) -> None:
                    for item in group.items:
                        if isinstance(item, ConditionGroup):
                            collect(item)
                        else:
                            seed.append(item)
                collect(rule.condition_root)
            elif rule.conditions:
                seed = list(rule.conditions)
        if seed:
            for c in seed:
                self._add_condition_row(c)
        else:
            self._add_condition_row()

        outer.addWidget(self._section_label("Action"))

        action_row = QHBoxLayout()
        self.action_type = QComboBox()
        for at in ACTION_TYPES:
            self.action_type.addItem(_ACTION_LABELS[at], userData=at)
        if rule and rule.action.type in ACTION_TYPES:
            self.action_type.setCurrentIndex(
                ACTION_TYPES.index(rule.action.type))
        self.action_type.currentIndexChanged.connect(self._action_changed)
        action_row.addWidget(self.action_type, stretch=1)

        self.action_target_combo = QComboBox()
        for cat in categories:
            self.action_target_combo.addItem(cat.name, userData=cat.id)
        action_row.addWidget(self.action_target_combo, stretch=2)

        self.action_target_edit = QLineEdit()
        self.action_target_edit.setPlaceholderText("Folder path")
        action_row.addWidget(self.action_target_edit, stretch=2)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setObjectName("secondary")
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.clicked.connect(self._browse_folder)
        action_row.addWidget(self.browse_btn)

        outer.addLayout(action_row)

        # Copy-vs-move replaces the old copy_to_* action variants.
        self.copy_check = QCheckBox(
            "Copy instead of move (leave the source file in place)")
        if rule:
            self.copy_check.setChecked(rule.is_copy)
        outer.addWidget(self.copy_check)

        rename_row = QHBoxLayout()
        rename_row.addWidget(QLabel("Rename to:"))
        self.rename_edit = QLineEdit(rule.action.rename_template if rule else "")
        self.rename_edit.setPlaceholderText(
            "Optional. Tokens: {stem} {ext} {name} {year} {month} {day}")
        rename_row.addWidget(self.rename_edit)
        outer.addLayout(rename_row)

        if rule and rule.action.type == "move_to_category":
            for i, cat in enumerate(categories):
                if cat.id == rule.action.target:
                    self.action_target_combo.setCurrentIndex(i)
                    break
        elif rule and rule.action.type == "move_to_folder":
            self.action_target_edit.setText(rule.action.target)
        self._action_changed()

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionLabel")
        return label

    def _add_condition_row(self, condition: Condition | None = None) -> None:
        row = _ConditionRow(condition, profile=self._profile)
        row.remove_btn.clicked.connect(lambda: self._remove_row(row))
        self._conditions_layout.addWidget(row)

    def _remove_row(self, row: _ConditionRow) -> None:
        self._conditions_layout.removeWidget(row)
        row.deleteLater()

    def _action_changed(self) -> None:
        at = self.action_type.currentData()
        wants_cat = at == "move_to_category"
        wants_folder = at == "move_to_folder"
        self.action_target_combo.setVisible(wants_cat)
        self.action_target_edit.setVisible(wants_folder)
        self.browse_btn.setVisible(wants_folder)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Pick destination")
        if folder:
            self.action_target_edit.setText(folder)

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip():
            self.name_edit.setFocus()
            return
        self.accept()

    def result_rule(self) -> Rule:
        """Build the final Rule. Only call after the dialog is accepted."""
        conditions: list[Condition] = []
        for i in range(self._conditions_layout.count()):
            row = self._conditions_layout.itemAt(i).widget()
            if isinstance(row, _ConditionRow):
                c = row.to_condition()
                if c.value or c.type in ("size_above_mb", "size_below_mb"):
                    conditions.append(c)

        at = self.action_type.currentData()
        if at == "move_to_category":
            target = self.action_target_combo.currentData() or ""
        elif at == "move_to_folder":
            target = self.action_target_edit.text().strip()
        else:
            target = ""
        action = Action(
            type=at, target=target,
            rename_template=self.rename_edit.text().strip(),
        )

        operator = self.operator_combo.currentData() or "and"
        root = ConditionGroup(operator=operator, items=list(conditions))
        is_copy = self.copy_check.isChecked()
        name = self.name_edit.text().strip()

        if self._original:
            self._original.name = name
            self._original.conditions = conditions  # keep flat in sync
            self._original.condition_root = root
            self._original.action = action
            self._original.is_copy = is_copy
            return self._original

        return Rule(
            id=uuid.uuid4().hex,
            name=name,
            enabled=True,
            conditions=conditions,
            condition_root=root,
            action=action,
            is_copy=is_copy,
        )
