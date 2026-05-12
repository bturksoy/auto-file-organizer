from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout

from app.ui.pages.base_page import BasePage, InfoBanner


class SettingsPage(BasePage):
    def __init__(self, parent=None) -> None:
        super().__init__(
            title="Settings",
            subtitle="Language, updates, organization mode, and background behavior.",
            parent=parent,
        )

    def build_body(self, layout: QVBoxLayout) -> None:
        layout.addWidget(InfoBanner(
            "Organization mode, language, auto-update preferences, "
            "background mode, and notifications. The full settings panel "
            "lands here in v2.0-alpha.6."
        ))
