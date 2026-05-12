"""Tiny dialog to name a new profile or rename an existing one."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLineEdit, QVBoxLayout, QLabel,
)


class ProfileNameDialog(QDialog):
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
