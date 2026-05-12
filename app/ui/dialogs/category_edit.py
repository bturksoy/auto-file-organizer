"""Modal dialog to create or edit a Category."""
from __future__ import annotations

import uuid

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog, QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from app.core.models import Category


class CategoryEditDialog(QDialog):
    def __init__(self, category: Category | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit category" if category else "New category")
        self.setMinimumWidth(420)

        self._color = category.color if category else "#7c8cff"
        self._original = category

        outer = QVBoxLayout(self)
        form = QFormLayout()
        outer.addLayout(form)

        self.name_edit = QLineEdit(category.name if category else "")
        self.name_edit.setPlaceholderText("e.g. Receipts")
        form.addRow("Name", self.name_edit)

        color_row = QWidget()
        color_layout = QVBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        self.color_button = QPushButton(self._color)
        self.color_button.setCursor(Qt.PointingHandCursor)
        self.color_button.clicked.connect(self._pick_color)
        self._apply_color_button_style()
        color_layout.addWidget(self.color_button)
        form.addRow("Color", color_row)

        self.ext_edit = QLineEdit(
            ", ".join(category.extensions) if category else "")
        self.ext_edit.setPlaceholderText(".pdf, .docx, .txt")
        form.addRow("Extensions", self.ext_edit)

        self.folder_edit = QLineEdit(
            category.target_folder if category else "")
        self.folder_edit.setPlaceholderText(
            "Subfolder name on disk (defaults to the category name)")
        form.addRow("Target folder", self.folder_edit)

        hint = QLabel(
            "Extensions are matched case-insensitively. Use a leading dot.")
        hint.setStyleSheet("color: #6b7079; font-size: 11px;")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(QColor(self._color), self, "Pick a color")
        if c.isValid():
            self._color = c.name()
            self.color_button.setText(self._color)
            self._apply_color_button_style()

    def _apply_color_button_style(self) -> None:
        self.color_button.setStyleSheet(
            f"background-color: {self._color};"
            " color: white;"
            " border: 1px solid #2c2e36;"
            " border-radius: 8px;"
            " padding: 6px 12px;"
        )

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip():
            self.name_edit.setFocus()
            return
        self.accept()

    def result_category(self) -> Category:
        name = self.name_edit.text().strip()
        extensions = [
            self._normalize_ext(e) for e in self.ext_edit.text().split(",")
            if e.strip()
        ]
        target = self.folder_edit.text().strip() or name
        if self._original:
            self._original.name = name
            self._original.color = self._color
            self._original.extensions = extensions
            self._original.target_folder = target
            return self._original
        return Category(
            id=uuid.uuid4().hex,
            name=name,
            color=self._color,
            extensions=extensions,
            target_folder=target,
            enabled=True,
            locked=False,
        )

    @staticmethod
    def _normalize_ext(raw: str) -> str:
        ext = raw.strip().lower()
        if not ext.startswith("."):
            ext = "." + ext
        return ext
