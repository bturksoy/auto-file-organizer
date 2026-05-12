"""Card widget that renders a single Category."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from app.core.models import Category
from app.ui.theme import active_palette, palette_signal
from app.ui.widgets.card import Card
from app.ui.widgets.chip import Chip
from app.ui.widgets.color_dot import ColorDot
from app.ui.widgets.flow_layout import FlowLayout
from app.ui.widgets.toggle import Toggle


class CategoryCard(Card):
    edit_requested = Signal(str)        # category_id
    delete_requested = Signal(str)
    toggled = Signal(str, bool)         # category_id, enabled

    def __init__(self, category: Category, parent=None) -> None:
        super().__init__(parent)
        self._category = category

        # Header row: toggle + dot + name + lock/edit/delete
        header = QHBoxLayout()
        header.setSpacing(10)

        self.toggle = Toggle(checked=category.enabled)
        self.toggle.toggled.connect(
            lambda v: self.toggled.emit(self._category.id, v))
        header.addWidget(self.toggle)

        self.dot = ColorDot(category.color, size=10)
        header.addWidget(self.dot)

        self.name_label = QLabel(category.name)
        self.name_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        header.addWidget(self.name_label)

        header.addStretch(1)

        if category.locked:
            lock = QLabel("🔒")
            lock.setStyleSheet("color: #6b7079;")
            lock.setToolTip("Built-in category (cannot be deleted)")
            header.addWidget(lock)
        else:
            self.edit_btn = QPushButton("✎")
            self.edit_btn.setObjectName("iconBtn")
            self.edit_btn.setCursor(Qt.PointingHandCursor)
            self.edit_btn.setFixedSize(30, 30)
            self.edit_btn.setToolTip("Edit category")
            self.edit_btn.clicked.connect(
                lambda: self.edit_requested.emit(self._category.id))
            header.addWidget(self.edit_btn)

            self.del_btn = QPushButton("✕")
            self.del_btn.setObjectName("iconBtn")
            self.del_btn.setProperty("class", "iconBtnDanger")
            self.del_btn.setCursor(Qt.PointingHandCursor)
            self.del_btn.setFixedSize(30, 30)
            self.del_btn.setToolTip("Delete category")
            self.del_btn.clicked.connect(
                lambda: self.delete_requested.emit(self._category.id))
            header.addWidget(self.del_btn)

        self.layout().addLayout(header)

        # Extension chips
        chip_holder = QWidget()
        chip_layout = FlowLayout(chip_holder, h_spacing=6, v_spacing=6)
        max_chips = 9
        for ext in category.extensions[:max_chips]:
            chip_layout.addWidget(Chip(ext))
        leftover = len(category.extensions) - max_chips
        if leftover > 0:
            chip_layout.addWidget(Chip(f"+{leftover} more"))
        if not category.extensions:
            chip_layout.addWidget(Chip("content-only"))
        self.layout().addWidget(chip_holder)

        # Target folder row
        target_row = QHBoxLayout()
        self._folder_icon = QLabel("📁")
        target_row.addWidget(self._folder_icon)
        self._target = QLabel(f"→ {category.target_folder or category.name}")
        target_row.addWidget(self._target)
        target_row.addStretch(1)
        self.layout().addLayout(target_row)

        self._restyle_text()
        palette_signal().connect(self._restyle_text)

    def _restyle_text(self) -> None:
        p = active_palette()
        self._folder_icon.setStyleSheet(f"color: {p.text_dim};")
        self._target.setStyleSheet(f"color: {p.text_dim}; font-size: 12px;")

    def category(self) -> Category:
        return self._category
