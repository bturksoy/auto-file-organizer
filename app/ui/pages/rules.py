from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout

from app.ui.pages.base_page import BasePage, InfoBanner


class RulesPage(BasePage):
    def __init__(self, parent=None) -> None:
        super().__init__(
            title="Rules",
            subtitle="User-defined conditions and actions, evaluated in order.",
            action_label="+ New Rule",
            parent=parent,
        )

    def build_body(self, layout: QVBoxLayout) -> None:
        layout.addWidget(InfoBanner(
            "Rules are checked in order from top to bottom. The first "
            "matching rule wins. Drag rules to reorder priority."
        ))
        placeholder = QLabel(
            "Rule cards, condition builder, and drag-to-reorder list "
            "land here in v2.0-alpha.3."
        )
        placeholder.setObjectName("pageSubtitle")
        placeholder.setWordWrap(True)
        layout.addWidget(placeholder)
