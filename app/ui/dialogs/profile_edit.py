"""Dialogs for naming or seeding profiles."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout,
)

from app.core.templates import template_choices


def _color_button(initial: str, *, on_change) -> tuple[QPushButton, dict]:
    """Make a swatch-style button that opens a color picker. Returns the
    button and a small holder dict so the caller can read the chosen value."""
    state = {"color": initial}

    btn = QPushButton(initial)
    btn.setCursor(Qt.PointingHandCursor)

    def apply_style() -> None:
        c = state["color"]
        btn.setText(c)
        btn.setStyleSheet(
            f"background-color: {c}; color: white;"
            " border: 1px solid #2c2e36; border-radius: 8px;"
            " padding: 6px 12px;"
        )
    apply_style()

    def pick() -> None:
        c = QColorDialog.getColor(QColor(state["color"]), btn, "Pick a color")
        if c.isValid():
            state["color"] = c.name()
            apply_style()
            on_change(state["color"])

    btn.clicked.connect(pick)
    return btn, state


class ProfileNameDialog(QDialog):
    """Rename an existing profile (optional color edit)."""

    def __init__(self, *, title: str = "Profile", initial: str = "",
                 initial_color: str = "#7c8cff", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Name"))
        self.name_edit = QLineEdit(initial)
        self.name_edit.setPlaceholderText("e.g. Work, Downloads, Photos")
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Color"))
        self._color_btn, self._color_state = _color_button(
            initial_color, on_change=lambda _: None)
        layout.addWidget(self._color_btn)

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

    def color(self) -> str:
        return self._color_state["color"]


class ProfileCreateDialog(QDialog):
    """Create a new profile from a template."""

    DEFAULT_COLORS = [
        "#7c8cff", "#22d3ee", "#34d399", "#fbbf24",
        "#fb923c", "#f472b6", "#a78bfa", "#94a3b8",
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New profile")
        self.setMinimumWidth(440)

        # Pick a different starting color each time for visual variety
        import random
        initial_color = random.choice(self.DEFAULT_COLORS)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Name"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Work")
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Color"))
        self._color_btn, self._color_state = _color_button(
            initial_color, on_change=lambda _: None)
        layout.addWidget(self._color_btn)

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

    def chosen_color(self) -> str:
        return self._color_state["color"]
