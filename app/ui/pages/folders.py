from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout

from app.ui.pages.base_page import BasePage, InfoBanner


class FoldersPage(BasePage):
    def __init__(self, parent=None) -> None:
        super().__init__(
            title="Folders",
            subtitle="Watched folders, destination library, and recent locations.",
            parent=parent,
        )

    def build_body(self, layout: QVBoxLayout) -> None:
        layout.addWidget(InfoBanner(
            "Folder management lands here: recent folders, the optional "
            "centralized destination library, and watched folders for "
            "background mode."
        ))
        placeholder = QLabel("v2.0-alpha.5")
        placeholder.setObjectName("pageSubtitle")
        layout.addWidget(placeholder)
