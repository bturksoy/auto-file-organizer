"""Modal dialog to create or edit a Rule (conditions + action)."""
from __future__ import annotations

import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from app.core.models import (
    ACTION_TYPES, CONDITION_TYPES, Action, Category, Condition, Rule,
)


_CONDITION_HELP = {
    "name_contains": "substring",
    "name_does_not_contain": "substring to exclude",
    "name_starts_with": "prefix",
    "name_ends_with": "suffix",
    "name_regex": "regex pattern",
    "extension_is": ".pdf",
    "extension_in": ".jpg, .png, .webp",
    "path_contains": "subfolder name in source path",
    "size_above_mb": "10",
    "size_below_mb": "10",
    "age_above_days": "30  (older than)",
    "age_below_days": "30  (newer than)",
}

_CONDITION_LABELS = {
    "name_contains": "Name contains",
    "name_does_not_contain": "Name does NOT contain",
    "name_starts_with": "Name starts with",
    "name_ends_with": "Name ends with",
    "name_regex": "Name matches regex",
    "extension_is": "Extension is",
    "extension_in": "Extension in list",
    "path_contains": "Source path contains",
    "size_above_mb": "Size above (MB)",
    "size_below_mb": "Size below (MB)",
    "age_above_days": "Age above (days)",
    "age_below_days": "Age below (days)",
}

_ACTION_LABELS = {
    "move_to_category": "Move to category",
    "move_to_folder": "Move to folder",
    "copy_to_category": "Copy to category",
    "copy_to_folder": "Copy to folder",
    "skip": "Skip (leave in place)",
}


class _ConditionRow(QWidget):
    def __init__(self, condition: Condition | None = None, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.type_combo = QComboBox()
        for ct in CONDITION_TYPES:
            self.type_combo.addItem(
                _CONDITION_LABELS.get(ct, ct.replace("_", " ").title()),
                userData=ct,
            )
        if condition and condition.type in CONDITION_TYPES:
            self.type_combo.setCurrentIndex(
                CONDITION_TYPES.index(condition.type))
        self.type_combo.currentIndexChanged.connect(self._update_placeholder)
        layout.addWidget(self.type_combo, stretch=1)

        self.value_edit = QLineEdit(condition.value if condition else "")
        self._update_placeholder()
        layout.addWidget(self.value_edit, stretch=2)

        self.remove_btn = QPushButton("×")
        self.remove_btn.setObjectName("secondary")
        self.remove_btn.setFixedSize(28, 28)
        self.remove_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.remove_btn)

    def _update_placeholder(self) -> None:
        ct = self.type_combo.currentData()
        self.value_edit.setPlaceholderText(_CONDITION_HELP.get(ct, ""))

    def to_condition(self) -> Condition:
        return Condition(
            type=self.type_combo.currentData(),
            value=self.value_edit.text().strip(),
        )


class RuleEditDialog(QDialog):
    def __init__(self, *, rule: Rule | None = None,
                 categories: list[Category], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit rule" if rule else "New rule")
        self.setMinimumWidth(540)

        self._original = rule
        self._categories = categories

        outer = QVBoxLayout(self)
        form = QFormLayout()
        outer.addLayout(form)

        self.name_edit = QLineEdit(rule.name if rule else "")
        self.name_edit.setPlaceholderText("e.g. Old invoices")
        form.addRow("Rule name", self.name_edit)

        outer.addWidget(self._section_label("Conditions (all must match)"))

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

        # Seed with the rule's existing conditions, or one empty row.
        if rule and rule.conditions:
            for c in rule.conditions:
                self._add_condition_row(c)
        else:
            self._add_condition_row()

        outer.addWidget(self._section_label("Action"))

        action_row = QHBoxLayout()
        self.action_type = QComboBox()
        for at in ACTION_TYPES:
            self.action_type.addItem(
                _ACTION_LABELS.get(at, at.replace("_", " ").title()),
                userData=at,
            )
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

        if rule and rule.action.type in ("move_to_category", "copy_to_category"):
            for i, cat in enumerate(categories):
                if cat.id == rule.action.target:
                    self.action_target_combo.setCurrentIndex(i)
                    break
        elif rule and rule.action.type in ("move_to_folder", "copy_to_folder"):
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
        row = _ConditionRow(condition)
        row.remove_btn.clicked.connect(lambda: self._remove_row(row))
        self._conditions_layout.addWidget(row)

    def _remove_row(self, row: _ConditionRow) -> None:
        self._conditions_layout.removeWidget(row)
        row.deleteLater()

    def _action_changed(self) -> None:
        at = self.action_type.currentData()
        wants_cat = at in ("move_to_category", "copy_to_category")
        wants_folder = at in ("move_to_folder", "copy_to_folder")
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
        conditions: list[Condition] = []
        for i in range(self._conditions_layout.count()):
            row = self._conditions_layout.itemAt(i).widget()
            if isinstance(row, _ConditionRow):
                c = row.to_condition()
                if c.value or c.type in ("size_above_mb", "size_below_mb"):
                    conditions.append(c)

        at = self.action_type.currentData()
        if at in ("move_to_category", "copy_to_category"):
            target = self.action_target_combo.currentData() or ""
        elif at in ("move_to_folder", "copy_to_folder"):
            target = self.action_target_edit.text().strip()
        else:
            target = ""
        action = Action(type=at, target=target)

        if self._original:
            self._original.name = self.name_edit.text().strip()
            self._original.conditions = conditions
            self._original.action = action
            return self._original

        return Rule(
            id=uuid.uuid4().hex,
            name=self.name_edit.text().strip(),
            enabled=True,
            conditions=conditions,
            action=action,
        )
