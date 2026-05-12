"""Settings page: organization mode + language + notifications + updates + auto."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QRadioButton, QSpinBox, QVBoxLayout,
    QComboBox,
)

from app.core.i18n import i18n
from app.core.models import ORG_MODES
from app.core.state import AppState
from app.ui.pages.base_page import BasePage
from app.ui.widgets.card import Card
from app.ui.widgets.toggle import Toggle


ORG_MODE_LABELS = {
    "rules_then_categories": (
        "Rules first, then categories",
        "Recommended - Rules are checked first, unmatched files use categories",
    ),
    "categories_only": (
        "Categories only",
        "Simple mode - Only use category-based organization",
    ),
    "rules_only": (
        "Rules only",
        "Advanced - Only files matching rules are organized",
    ),
}


class SettingsPage(BasePage):
    def __init__(self, state: AppState, parent=None) -> None:
        self._state = state
        super().__init__(
            title="Settings",
            subtitle="Active-profile behavior and global preferences.",
            parent=parent,
        )
        state.active_profile_changed.connect(self._sync)
        state.profiles_changed.connect(self._sync)
        self._sync()

    def build_body(self, layout: QVBoxLayout) -> None:
        layout.addWidget(self._build_mode_card())
        layout.addWidget(self._build_scan_card())
        layout.addWidget(self._build_notifications_card())
        layout.addWidget(self._build_auto_card())
        layout.addWidget(self._build_language_card())
        layout.addWidget(self._build_updates_card())

    def _build_scan_card(self) -> Card:
        card = Card()
        card.layout().addWidget(self._h2("SCANNING"))

        row1 = QHBoxLayout()
        title = QLabel("Recursive scan (include subfolders)")
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        row1.addWidget(title)
        row1.addStretch(1)
        self._recursive_toggle = Toggle()
        self._recursive_toggle.toggled.connect(self._on_recursive_toggled)
        row1.addWidget(self._recursive_toggle)
        card.layout().addLayout(row1)

        hint1 = QLabel(
            "When on, the scanner descends into subfolders but never enters "
            "category folders this profile owns. Useful for flattening a "
            "messy tree."
        )
        hint1.setStyleSheet("color: #9ba0ab;")
        hint1.setWordWrap(True)
        card.layout().addWidget(hint1)

        row2 = QHBoxLayout()
        title2 = QLabel("Inspect PDF / DOCX content for CV detection")
        title2.setStyleSheet("font-size: 14px; font-weight: 600;")
        row2.addWidget(title2)
        row2.addStretch(1)
        self._pdf_toggle = Toggle()
        self._pdf_toggle.toggled.connect(self._on_pdf_toggled)
        row2.addWidget(self._pdf_toggle)
        card.layout().addLayout(row2)

        hint2 = QLabel(
            "Opens PDFs and Word documents to find CV-like keywords. Turn "
            "off if you want a faster scan and never want content inspection."
        )
        hint2.setStyleSheet("color: #9ba0ab;")
        hint2.setWordWrap(True)
        card.layout().addWidget(hint2)
        return card

    def _on_recursive_toggled(self, value: bool) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        profile.settings.recursive_scan = value
        self._state.save()

    def _on_pdf_toggled(self, value: bool) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        profile.settings.inspect_pdf_docx = value
        self._state.save()

    # ----- cards -----

    def _build_mode_card(self) -> Card:
        card = Card()
        card.layout().addWidget(self._h2("ORGANIZATION MODE"))
        sub = QLabel("Choose how files are matched for organization")
        sub.setStyleSheet("color: #9ba0ab;")
        card.layout().addWidget(sub)

        self._mode_group = QButtonGroup(card)
        self._mode_buttons: dict[str, QRadioButton] = {}
        for mode in ORG_MODES:
            label, hint = ORG_MODE_LABELS[mode]
            btn = QRadioButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.toggled.connect(
                lambda checked, m=mode: checked and self._set_mode(m))
            self._mode_group.addButton(btn)
            self._mode_buttons[mode] = btn
            wrap = QVBoxLayout()
            wrap.addWidget(btn)
            hint_label = QLabel(hint)
            hint_label.setStyleSheet("color: #9ba0ab; padding-left: 24px;")
            wrap.addWidget(hint_label)
            card.layout().addLayout(wrap)
        return card

    def _build_notifications_card(self) -> Card:
        card = Card()
        header = QHBoxLayout()
        body = QVBoxLayout()
        body.addWidget(self._h2("NOTIFICATIONS"))
        title = QLabel("Show notifications when organizing")
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        body.addWidget(title)
        hint = QLabel("Display a notification when files are organized")
        hint.setStyleSheet("color: #9ba0ab;")
        body.addWidget(hint)
        header.addLayout(body, stretch=1)
        self._notif_toggle = Toggle()
        self._notif_toggle.toggled.connect(self._on_notif_toggled)
        header.addWidget(self._notif_toggle, alignment=Qt.AlignVCenter)
        card.layout().addLayout(header)
        return card

    def _build_auto_card(self) -> Card:
        card = Card()
        card.layout().addWidget(self._h2("BACKGROUND MODE"))
        row1 = QHBoxLayout()
        title = QLabel("Enable scheduled auto-organize")
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        row1.addWidget(title)
        row1.addStretch(1)
        self._auto_toggle = Toggle()
        self._auto_toggle.toggled.connect(self._on_auto_toggled)
        row1.addWidget(self._auto_toggle)
        card.layout().addLayout(row1)

        hint = QLabel(
            "The app keeps a tray icon and re-organizes the watched folder "
            "(set on the Folders tab) on the chosen interval."
        )
        hint.setStyleSheet("color: #9ba0ab;")
        hint.setWordWrap(True)
        card.layout().addWidget(hint)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Interval (minutes):"))
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 1440)
        self._interval_spin.valueChanged.connect(self._on_interval_changed)
        row2.addWidget(self._interval_spin)
        row2.addStretch(1)

        self._tray_start_toggle = Toggle()
        self._tray_start_toggle.toggled.connect(self._on_tray_start_toggled)
        row2.addWidget(QLabel("Start in tray:"))
        row2.addWidget(self._tray_start_toggle)
        card.layout().addLayout(row2)
        return card

    def _build_language_card(self) -> Card:
        card = Card()
        row = QHBoxLayout()
        body = QVBoxLayout()
        body.addWidget(self._h2("LANGUAGE"))
        body.addWidget(QLabel("Interface language"))
        row.addLayout(body, stretch=1)
        self._lang_combo = QComboBox()
        for code, name in i18n.languages.items():
            self._lang_combo.addItem(name, userData=code)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        row.addWidget(self._lang_combo)
        card.layout().addLayout(row)
        return card

    def _build_updates_card(self) -> Card:
        card = Card()
        row = QHBoxLayout()
        body = QVBoxLayout()
        body.addWidget(self._h2("UPDATES"))
        body.addWidget(QLabel("Check for updates on startup"))
        row.addLayout(body, stretch=1)
        self._updates_toggle = Toggle()
        self._updates_toggle.toggled.connect(self._on_updates_toggled)
        row.addWidget(self._updates_toggle)
        card.layout().addLayout(row)
        return card

    @staticmethod
    def _h2(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionLabel")
        return label

    # ----- sync from state -----

    def _sync(self) -> None:
        profile = self._state.active_profile()
        if profile is None:
            return
        s = profile.settings
        if s.organization_mode in self._mode_buttons:
            self._mode_buttons[s.organization_mode].setChecked(True)
        self._notif_toggle.setChecked(s.show_notifications)
        self._auto_toggle.setChecked(s.auto_organize)
        self._interval_spin.setValue(s.auto_interval_min)
        self._tray_start_toggle.setChecked(s.start_in_tray)
        self._recursive_toggle.setChecked(s.recursive_scan)
        self._pdf_toggle.setChecked(s.inspect_pdf_docx)
        # Language
        for i in range(self._lang_combo.count()):
            if self._lang_combo.itemData(i) == self._state.data.language:
                self._lang_combo.setCurrentIndex(i)
                break
        self._updates_toggle.setChecked(self._state.data.check_updates_on_startup)

    # ----- handlers -----

    def _set_mode(self, mode: str) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        profile.settings.organization_mode = mode
        self._state.save()

    def _on_notif_toggled(self, value: bool) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        profile.settings.show_notifications = value
        self._state.save()

    def _on_auto_toggled(self, value: bool) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        profile.settings.auto_organize = value
        self._state.save()

    def _on_interval_changed(self, value: int) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        profile.settings.auto_interval_min = max(1, int(value))
        self._state.save()

    def _on_tray_start_toggled(self, value: bool) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        profile.settings.start_in_tray = value
        self._state.save()

    def _on_language_changed(self, _index: int) -> None:
        code = self._lang_combo.currentData()
        if code:
            self._state.set_language(code)

    def _on_updates_toggled(self, value: bool) -> None:
        self._state.data.check_updates_on_startup = value
        self._state.save()
