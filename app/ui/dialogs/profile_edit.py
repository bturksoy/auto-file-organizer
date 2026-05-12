"""Dialogs for naming or seeding profiles."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout,
)

from app.core.templates import template_choices


class ProfileNameDialog(QDialog):
    """Plain rename / quick-create dialog (no template choice)."""

    def __init__(self, *, title: str = "Profile", initial: str = "",
                 parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Name"))
        self.name_edit = QLineEdit(initial)
        self.name_edit.setPlaceholderText("e.g. Work, Downloads, Photos")
        layout.addWidget(self.name_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept_if_named)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_named(self) -> None:
        if self.name_edit.text().strip():
            self.accept()
        else:
            self.name_edit.setFocus()

    def value(self) -> str:
        return self.name_edit.text().strip()


class ProfileCreateDialog(QDialog):
    """Create a new profile from a template."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New profile")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Name"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Work")
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Start from"))
        self.template_combo = QComboBox()
        for key, label in template_choices():
            self.template_combo.addItem(label, userData=key)
        layout.addWidget(self.template_combo)

        hint = QLabel(
            "Templates pre-fill rules and category target folders. You can "
            "edit everything afterwards.")
        hint.setStyleSheet("color: #9ba0ab;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept_if_named)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_named(self) -> None:
        if self.name_edit.text().strip():
            self.accept()
        else:
            self.name_edit.setFocus()

    def chosen_name(self) -> str:
        return self.name_edit.text().strip()

    def chosen_template(self) -> str:
        return self.template_combo.currentData() or "empty"
