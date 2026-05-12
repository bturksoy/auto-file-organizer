"""Modal dialog to create or edit a Rule (conditions + action)."""
from __future__ import annotations

import uuid

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from app.core.classifier import _file_meta, _rule_matches
from app.core.models import (
    ACTION_TYPES, CONDITION_TYPES, Action, Category, Condition,
    ConditionGroup, Profile, Rule,
)


class _TestBridge(QObject):
    """Bridge for marshalling test-rule counts back to the GUI thread."""
    counted = Signal(int)


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
    "modified_after": "2024-01-01",
    "modified_before": "2024-12-31",
    "content_matches": "Pick a pattern from Content tab",
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
    "modified_after": "Modified after (YYYY-MM-DD)",
    "modified_before": "Modified before (YYYY-MM-DD)",
    "content_matches": "Content matches pattern",
}

_ACTION_LABELS = {
    "move_to_category": "Move to category",
    "move_to_folder": "Move to folder",
    "copy_to_category": "Copy to category",
    "copy_to_folder": "Copy to folder",
    "skip": "Skip (leave in place)",
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
            self.type_combo.addItem(
                _CONDITION_LABELS.get(ct, ct.replace("_", " ").title()),
                userData=ct,
            )
        if condition and condition.type in CONDITION_TYPES:
            self.type_combo.setCurrentIndex(
                CONDITION_TYPES.index(condition.type))
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
    def __init__(self, *, rule: Rule | None = None,
                 categories: list[Category],
                 profile: Profile | None = None,
                 test_folder: Path | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit rule" if rule else "New rule")
        self.setMinimumWidth(580)

        self._original = rule
        self._categories = categories
        self._profile = profile
        self._test_folder = test_folder
        self._test_bridge = _TestBridge()
        self._test_bridge.counted.connect(self._on_test_counted)

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

        # Seed with the rule's existing conditions (prefer the tree if set),
        # or with one empty row when creating a new rule. Nested groups
        # collapse to their leaves — the UI is flat for now.
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

        rename_row = QHBoxLayout()
        rename_row.addWidget(QLabel("Rename to:"))
        self.rename_edit = QLineEdit(rule.action.rename_template if rule else "")
        self.rename_edit.setPlaceholderText(
            "Optional. Tokens: {stem} {ext} {name} {year} {month} {day}")
        rename_row.addWidget(self.rename_edit)
        outer.addLayout(rename_row)

        if rule and rule.action.type in ("move_to_category", "copy_to_category"):
            for i, cat in enumerate(categories):
                if cat.id == rule.action.target:
                    self.action_target_combo.setCurrentIndex(i)
                    break
        elif rule and rule.action.type in ("move_to_folder", "copy_to_folder"):
            self.action_target_edit.setText(rule.action.target)
        self._action_changed()

        # Live test row — runs the in-progress rule against the current
        # folder and shows the match count.
        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Test against current folder")
        self._test_btn.setObjectName("secondary")
        self._test_btn.setCursor(Qt.PointingHandCursor)
        self._test_btn.clicked.connect(self._run_test)
        if not self._test_folder:
            self._test_btn.setEnabled(False)
            self._test_btn.setToolTip(
                "Pick a folder in the main window first to enable testing.")
        test_row.addWidget(self._test_btn)
        self._test_result = QLabel("")
        self._test_result.setStyleSheet("color: #9ba0ab; padding-left: 10px;")
        test_row.addWidget(self._test_result, stretch=1)
        outer.addLayout(test_row)

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
        wants_cat = at in ("move_to_category", "copy_to_category")
        wants_folder = at in ("move_to_folder", "copy_to_folder")
        self.action_target_combo.setVisible(wants_cat)
        self.action_target_edit.setVisible(wants_folder)
        self.browse_btn.setVisible(wants_folder)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Pick destination")
        if folder:
            self.action_target_edit.setText(folder)

    def _run_test(self) -> None:
        if not self._test_folder or not self._test_folder.is_dir():
            return
        rule = self.result_rule()
        # Don't mutate the original until the dialog is saved.
        if self._original is not None:
            import copy as _copy
            rule = _copy.copy(rule)
        self._test_result.setText("Scanning...")
        self._test_btn.setEnabled(False)
        folder = self._test_folder

        def work() -> None:
            count = 0
            try:
                for entry in folder.iterdir():
                    if not entry.is_file():
                        continue
                    if entry.name.startswith("."):
                        continue
                    if _rule_matches(rule, _file_meta(entry)):
                        count += 1
            except OSError:
                pass
            self._test_bridge.counted.emit(count)
        threading.Thread(target=work, daemon=True).start()

    def _on_test_counted(self, count: int) -> None:
        if count == 0:
            self._test_result.setText("No matches in the current folder.")
        elif count == 1:
            self._test_result.setText("1 file would match.")
        else:
            self._test_result.setText(f"{count} files would match.")
        self._test_btn.setEnabled(True)

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
        action = Action(
            type=at, target=target,
            rename_template=self.rename_edit.text().strip(),
        )

        operator = self.operator_combo.currentData() or "and"
        root = ConditionGroup(operator=operator, items=list(conditions))

        if self._original:
            self._original.name = self.name_edit.text().strip()
            self._original.conditions = conditions  # keep flat in sync
            self._original.condition_root = root
            self._original.action = action
            return self._original

        return Rule(
            id=uuid.uuid4().hex,
            name=self.name_edit.text().strip(),
            enabled=True,
            conditions=conditions,
            condition_root=root,
            action=action,
        )
