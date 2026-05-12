from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout

from app.ui.pages.base_page import BasePage, InfoBanner


class ProfilesPage(BasePage):
    def __init__(self, parent=None) -> None:
        super().__init__(
            title="Profiles",
            subtitle="Save and switch between different organization configurations.",
            action_label="+ New Profile",
            parent=parent,
        )

    def build_body(self, layout: QVBoxLayout) -> None:
        layout.addWidget(InfoBanner(
            "Each profile contains its own rules, categories, and settings. "
            "Switch profiles to use different organization configurations for "
            "different purposes."
        ))
        placeholder = QLabel(
            "Profile list with switch / rename / export / delete actions "
            "lands here in v2.0-alpha.4."
        )
        placeholder.setObjectName("pageSubtitle")
        placeholder.setWordWrap(True)
        layout.addWidget(placeholder)
