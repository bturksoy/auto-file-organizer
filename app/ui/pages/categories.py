from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout

from app.ui.pages.base_page import BasePage, InfoBanner


class CategoriesPage(BasePage):
    def __init__(self, parent=None) -> None:
        super().__init__(
            title="Categories",
            subtitle="Extension-based groupings and their target folders.",
            action_label="+ New Category",
            parent=parent,
        )

    def build_body(self, layout: QVBoxLayout) -> None:
        layout.addWidget(InfoBanner(
            "Each category has a name, color, list of file extensions, and "
            "a target folder. Built-in categories are locked but can be "
            "toggled on or off."
        ))
        placeholder = QLabel(
            "Category cards with extension chips and target-folder editor "
            "land here in v2.0-alpha.2."
        )
        placeholder.setObjectName("pageSubtitle")
        placeholder.setWordWrap(True)
        layout.addWidget(placeholder)
