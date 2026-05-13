"""Card widget that renders a single Category. Reorder via ↑↓ arrows."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QWidget,
)

from app.core.i18n import i18n
from app.core.models import Category
from app.ui.icons import make_icon, make_pixmap
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
    move_up_requested = Signal(str)
    move_down_requested = Signal(str)

    def __init__(self, category: Category, *, can_move_up: bool = True,
                 can_move_down: bool = True, parent=None) -> None:
        super().__init__(parent)
        self._category = category

        # Header row: arrows + toggle + dot + name + lock/edit/delete
        header = QHBoxLayout()
        header.setSpacing(8)

        if not category.locked:
            self._up_btn = self._mk_icon_button(i18n.t("widget.tooltip.move_up"))
            self._up_btn.clicked.connect(
                lambda: self.move_up_requested.emit(self._category.id))
            self._up_btn.setEnabled(can_move_up)
            header.addWidget(self._up_btn)

            self._down_btn = self._mk_icon_button(i18n.t("widget.tooltip.move_down"))
            self._down_btn.clicked.connect(
                lambda: self.move_down_requested.emit(self._category.id))
            self._down_btn.setEnabled(can_move_down)
            header.addWidget(self._down_btn)

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
            self._lock = QLabel()
            self._lock.setFixedSize(20, 20)
            self._lock.setToolTip(i18n.t("widget.category_card.locked_tooltip"))
            header.addWidget(self._lock)
        else:
            self.edit_btn = self._mk_icon_button(
                i18n.t("widget.tooltip.edit_category"))
            self.edit_btn.clicked.connect(
                lambda: self.edit_requested.emit(self._category.id))
            header.addWidget(self.edit_btn)

            self.del_btn = self._mk_icon_button(
                i18n.t("widget.tooltip.delete_category"))
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
            chip_layout.addWidget(Chip(
                i18n.t("widget.category_card.more_chips", n=leftover)))
        if not category.extensions:
            chip_layout.addWidget(Chip(
                i18n.t("widget.category_card.content_only")))
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

    @staticmethod
    def _mk_icon_button(tooltip: str) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("iconBtn")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedSize(30, 30)
        btn.setIconSize(QSize(16, 16))
        btn.setToolTip(tooltip)
        return btn

    def _restyle_text(self) -> None:
        p = active_palette()
        self._folder_icon.setStyleSheet(f"color: {p.text_dim};")
        self._target.setStyleSheet(f"color: {p.text_dim}; font-size: 12px;")
        # Repaint icons
        if hasattr(self, "_lock"):
            self._lock.setPixmap(
                make_pixmap("lock", size=18, color=p.text_faint))
        if hasattr(self, "_up_btn"):
            self._up_btn.setIcon(make_icon("chevron_up", color=p.text_dim))
        if hasattr(self, "_down_btn"):
            self._down_btn.setIcon(make_icon("chevron_down", color=p.text_dim))
        if hasattr(self, "edit_btn"):
            self.edit_btn.setIcon(make_icon("pencil", color=p.text_dim))
        if hasattr(self, "del_btn"):
            self.del_btn.setIcon(make_icon("cross", color=p.text_dim))

    def category(self) -> Category:
        return self._category
