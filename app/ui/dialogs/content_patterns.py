"""Manage user-defined content patterns (keyword detectors for PDF/DOCX).

Mirrors the built-in CV detector: each pattern has a list of strong
keywords (any hit -> match) and weak keywords (need `weak_threshold`
hits). Patterns are referenced by id from rule conditions of type
"content_matches".
"""
from __future__ import annotations

import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSpinBox,
    QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from app.core.i18n import i18n
from app.core.models import ContentPattern, Profile


def _csv_to_list(text: str) -> list[str]:
    return [t.strip() for t in text.replace("\n", ",").split(",") if t.strip()]


def _list_to_csv(values: list[str]) -> str:
    return ", ".join(values)


class ContentPatternsDialog(QDialog):
    """Two-pane editor: left list of patterns, right form for selected."""

    def __init__(self, profile: Profile, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.t("dialog.content_patterns.title"))
        self.setMinimumSize(720, 480)
        self._profile = profile
        # Work on a clone so Cancel discards everything cleanly.
        self._patterns: list[ContentPattern] = [
            ContentPattern(
                id=p.id, name=p.name,
                strong=list(p.strong), weak=list(p.weak),
                weak_threshold=p.weak_threshold,
            )
            for p in profile.content_patterns
        ]
        self._current: ContentPattern | None = None

        self._build_ui()
        if self._patterns:
            self._list.setCurrentRow(0)
        else:
            self._sync_form()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        intro = QLabel(i18n.t("dialog.content_patterns.intro"))
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #9ba0ab;")
        outer.addWidget(intro)

        split = QSplitter(Qt.Horizontal)
        outer.addWidget(split, stretch=1)

        # ----- Left pane: list + add/remove --------------------------------
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        left_layout.addWidget(self._list, stretch=1)

        btn_row = QHBoxLayout()
        add_btn = QPushButton(i18n.t("dialog.content_patterns.new_btn"))
        add_btn.clicked.connect(self._add_pattern)
        rm_btn = QPushButton(i18n.t("action.remove"))
        rm_btn.clicked.connect(self._remove_pattern)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        left_layout.addLayout(btn_row)
        split.addWidget(left)

        # ----- Right pane: form for selected pattern -----------------------
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)

        right_layout.addWidget(QLabel(i18n.t("common.name")))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(
            i18n.t("dialog.content_patterns.placeholder.name"))
        self._name_edit.textChanged.connect(self._on_name_changed)
        right_layout.addWidget(self._name_edit)

        right_layout.addWidget(QLabel(i18n.t("dialog.content_patterns.strong_label")))
        self._strong_edit = QTextEdit()
        self._strong_edit.setPlaceholderText(
            i18n.t("dialog.content_patterns.placeholder.strong"))
        self._strong_edit.setFixedHeight(80)
        self._strong_edit.textChanged.connect(self._on_strong_changed)
        right_layout.addWidget(self._strong_edit)

        right_layout.addWidget(QLabel(i18n.t("dialog.content_patterns.weak_label")))
        self._weak_edit = QTextEdit()
        self._weak_edit.setPlaceholderText(
            i18n.t("dialog.content_patterns.placeholder.weak"))
        self._weak_edit.setFixedHeight(80)
        self._weak_edit.textChanged.connect(self._on_weak_changed)
        right_layout.addWidget(self._weak_edit)

        thresh_row = QHBoxLayout()
        thresh_row.addWidget(QLabel(i18n.t("dialog.content_patterns.weak_thresh_label")))
        self._thresh_spin = QSpinBox()
        self._thresh_spin.setRange(1, 20)
        self._thresh_spin.valueChanged.connect(self._on_thresh_changed)
        thresh_row.addWidget(self._thresh_spin)
        thresh_row.addStretch(1)
        right_layout.addLayout(thresh_row)

        right_layout.addStretch(1)
        split.addWidget(right)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._refresh_list()

    # ----- list management -------------------------------------------------

    def _refresh_list(self) -> None:
        row = self._list.currentRow()
        self._list.blockSignals(True)
        self._list.clear()
        for p in self._patterns:
            item = QListWidgetItem(self._label(p.name))
            self._list.addItem(item)
        self._list.blockSignals(False)
        if self._patterns:
            idx = min(max(row, 0), len(self._patterns) - 1)
            self._list.setCurrentRow(idx)
        else:
            self._current = None
            self._sync_form()

    def _label(self, name: str) -> str:
        return name or i18n.t("common.unnamed")

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._patterns):
            self._current = self._patterns[row]
        else:
            self._current = None
        self._sync_form()

    def _add_pattern(self) -> None:
        name, ok = QInputDialog.getText(
            self, i18n.t("dialog.content_patterns.new_title"),
            i18n.t("dialog.content_patterns.new_prompt"))
        if not ok or not name.strip():
            return
        p = ContentPattern(
            id=uuid.uuid4().hex, name=name.strip(),
            strong=[], weak=[], weak_threshold=2,
        )
        self._patterns.append(p)
        self._refresh_list()
        self._list.setCurrentRow(len(self._patterns) - 1)

    def _remove_pattern(self) -> None:
        if self._current is None:
            return
        confirm = QMessageBox.question(
            self, i18n.t("dialog.content_patterns.remove_title"),
            i18n.t("dialog.content_patterns.remove_body",
                   name=self._current.name),
        )
        if confirm != QMessageBox.Yes:
            return
        self._patterns = [p for p in self._patterns if p is not self._current]
        self._refresh_list()

    # ----- form sync -------------------------------------------------------

    def _sync_form(self) -> None:
        # Disable the form when no pattern is selected.
        has = self._current is not None
        for w in (self._name_edit, self._strong_edit,
                  self._weak_edit, self._thresh_spin):
            w.setEnabled(has)
        if not has:
            self._name_edit.blockSignals(True)
            self._name_edit.clear()
            self._name_edit.blockSignals(False)
            self._strong_edit.blockSignals(True)
            self._strong_edit.clear()
            self._strong_edit.blockSignals(False)
            self._weak_edit.blockSignals(True)
            self._weak_edit.clear()
            self._weak_edit.blockSignals(False)
            return
        p = self._current
        self._name_edit.blockSignals(True)
        self._name_edit.setText(p.name)
        self._name_edit.blockSignals(False)
        self._strong_edit.blockSignals(True)
        self._strong_edit.setPlainText(_list_to_csv(p.strong))
        self._strong_edit.blockSignals(False)
        self._weak_edit.blockSignals(True)
        self._weak_edit.setPlainText(_list_to_csv(p.weak))
        self._weak_edit.blockSignals(False)
        self._thresh_spin.blockSignals(True)
        self._thresh_spin.setValue(p.weak_threshold)
        self._thresh_spin.blockSignals(False)

    def _on_name_changed(self, text: str) -> None:
        if self._current is None:
            return
        self._current.name = text.strip()
        # Update list label without losing selection.
        row = self._list.currentRow()
        if 0 <= row < self._list.count():
            self._list.item(row).setText(self._label(self._current.name))

    def _on_strong_changed(self) -> None:
        if self._current is None:
            return
        self._current.strong = _csv_to_list(self._strong_edit.toPlainText())

    def _on_weak_changed(self) -> None:
        if self._current is None:
            return
        self._current.weak = _csv_to_list(self._weak_edit.toPlainText())

    def _on_thresh_changed(self, value: int) -> None:
        if self._current is None:
            return
        self._current.weak_threshold = max(1, int(value))

    # ----- result ----------------------------------------------------------

    def result_patterns(self) -> list[ContentPattern]:
        """Return the edited pattern list (caller assigns to profile)."""
        return [p for p in self._patterns if p.name.strip()]
