from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout

from app.ui.pages.base_page import BasePage, InfoBanner


class HomePage(BasePage):
    def __init__(self, parent=None) -> None:
        super().__init__(
            title="Home",
            subtitle="Preview and run the active profile against the selected folder.",
            parent=parent,
        )

    def build_body(self, layout: QVBoxLayout) -> None:
        banner = InfoBanner(
            "Welcome. Pick a folder from the top-right picker, then use "
            "Preview to see how the active profile will classify your files. "
            "Rules and categories are defined in their own tabs."
        )
        layout.addWidget(banner)

        placeholder = QLabel(
            "Home dashboard widgets (preview, run, last operation, stats) "
            "will land here in v2.0-alpha.5."
        )
        placeholder.setObjectName("pageSubtitle")
        placeholder.setWordWrap(True)
        layout.addWidget(placeholder)
