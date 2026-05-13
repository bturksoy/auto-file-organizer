"""Settings page: organization mode + language + notifications + updates + auto."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QHBoxLayout, QLabel, QPushButton, QRadioButton,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from app.core.i18n import i18n
from app.core.models import ORG_MODES
from app.core.state import AppState
from app.ui.dialogs.content_patterns import ContentPatternsDialog
from app.ui.pages.base_page import BasePage
from app.ui.widgets.card import Card
from app.ui.widgets.toggle import Toggle


# Org-mode labels come from i18n: settings.org_mode.<id>.label / .hint.


class SettingsPage(BasePage):
    def __init__(self, state: AppState, parent=None) -> None:
        self._state = state
        super().__init__(
            title=i18n.t("page_settings_title"),
            subtitle=i18n.t("page_settings_subtitle"),
            parent=parent,
        )
        state.active_profile_changed.connect(self._sync)
        state.profiles_changed.connect(self._sync)
        self._sync()

    def build_body(self, layout: QVBoxLayout) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Remove the trailing addStretch the BasePage installed: cards must
        # sit at the top of the scroll, otherwise the scroll viewport pushes
        # them off-screen with the parent layout's stretch.
        layout.addWidget(scroll, stretch=1)

        inner = QWidget()
        body = QVBoxLayout(inner)
        body.setContentsMargins(0, 0, 6, 0)
        body.setSpacing(14)
        for builder in (
            self._build_mode_card,
            self._build_scan_card,
            self._build_content_patterns_card,
            self._build_notifications_card,
            self._build_auto_card,
            self._build_theme_card,
            self._build_language_card,
            self._build_updates_card,
        ):
            body.addWidget(builder())
        body.addStretch(1)
        scroll.setWidget(inner)

    def _build_scan_card(self) -> Card:
        card = Card()
        card.layout().addWidget(self._h2(i18n.t("page.settings.section_scanning")))

        row1 = QHBoxLayout()
        title = QLabel(i18n.t("page.settings.recursive_title"))
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        row1.addWidget(title)
        row1.addStretch(1)
        self._recursive_toggle = Toggle()
        self._recursive_toggle.toggled.connect(self._on_recursive_toggled)
        row1.addWidget(self._recursive_toggle)
        card.layout().addLayout(row1)

        hint1 = QLabel(i18n.t("page.settings.recursive_hint"))
        hint1.setStyleSheet("color: #9ba0ab;")
        hint1.setWordWrap(True)
        card.layout().addWidget(hint1)

        row2 = QHBoxLayout()
        title2 = QLabel(i18n.t("page.settings.pdf_inspect_title"))
        title2.setStyleSheet("font-size: 14px; font-weight: 600;")
        row2.addWidget(title2)
        row2.addStretch(1)
        self._pdf_toggle = Toggle()
        self._pdf_toggle.toggled.connect(self._on_pdf_toggled)
        row2.addWidget(self._pdf_toggle)
        card.layout().addLayout(row2)

        hint2 = QLabel(i18n.t("page.settings.pdf_inspect_hint"))
        hint2.setStyleSheet("color: #9ba0ab;")
        hint2.setWordWrap(True)
        card.layout().addWidget(hint2)
        return card

    def _build_content_patterns_card(self) -> Card:
        card = Card()
        card.layout().addWidget(self._h2(i18n.t("page.settings.section_content_patterns")))
        hint = QLabel(i18n.t("page.settings.content_patterns_hint"))
        hint.setStyleSheet("color: #9ba0ab;")
        hint.setWordWrap(True)
        card.layout().addWidget(hint)

        self._patterns_count_label = QLabel("")
        self._patterns_count_label.setStyleSheet(
            "font-size: 13px; padding-top: 4px;")
        card.layout().addWidget(self._patterns_count_label)

        row = QHBoxLayout()
        row.addStretch(1)
        btn = QPushButton(i18n.t("page.settings.manage_patterns_btn"))
        btn.clicked.connect(self._open_patterns_dialog)
        row.addWidget(btn)
        card.layout().addLayout(row)
        return card

    def _open_patterns_dialog(self) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        dlg = ContentPatternsDialog(profile, parent=self)
        if dlg.exec():
            profile.content_patterns = dlg.result_patterns()
            self._state.save()
            self._sync()

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
        card.layout().addWidget(self._h2(i18n.t("page.settings.section_org_mode")))
        sub = QLabel(i18n.t("page.settings.org_mode_hint"))
        sub.setStyleSheet("color: #9ba0ab;")
        card.layout().addWidget(sub)

        self._mode_group = QButtonGroup(card)
        self._mode_buttons: dict[str, QRadioButton] = {}
        for mode in ORG_MODES:
            label = i18n.t(f"settings.org_mode.{mode}.label")
            hint = i18n.t(f"settings.org_mode.{mode}.hint")
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
        body.addWidget(self._h2(i18n.t("page.settings.section_notifications")))
        title = QLabel(i18n.t("page.settings.notif_title"))
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        body.addWidget(title)
        hint = QLabel(i18n.t("page.settings.notif_hint"))
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
        card.layout().addWidget(self._h2(i18n.t("page.settings.section_background")))
        hint = QLabel(i18n.t("page.settings.background_hint"))
        hint.setStyleSheet("color: #9ba0ab;")
        hint.setWordWrap(True)
        card.layout().addWidget(hint)

        self._bg_group = QButtonGroup(card)
        self._bg_buttons: dict[str, QRadioButton] = {}
        for key in ("off", "scheduled", "realtime"):
            label = i18n.t(f"page.settings.bg_mode.{key}.label")
            desc = i18n.t(f"page.settings.bg_mode.{key}.hint")
            btn = QRadioButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.toggled.connect(
                lambda checked, k=key: checked and self._set_bg_mode(k))
            self._bg_group.addButton(btn)
            self._bg_buttons[key] = btn
            wrap = QVBoxLayout()
            wrap.addWidget(btn)
            sub = QLabel(desc)
            sub.setStyleSheet("color: #9ba0ab; padding-left: 24px;")
            sub.setWordWrap(True)
            wrap.addWidget(sub)
            card.layout().addLayout(wrap)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel(i18n.t("page.settings.bg_interval_label")))
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 1440)
        self._interval_spin.valueChanged.connect(self._on_interval_changed)
        row2.addWidget(self._interval_spin)
        row2.addStretch(1)

        self._tray_start_toggle = Toggle()
        self._tray_start_toggle.toggled.connect(self._on_tray_start_toggled)
        row2.addWidget(QLabel(i18n.t("page.settings.start_in_tray_label")))
        row2.addWidget(self._tray_start_toggle)
        card.layout().addLayout(row2)
        return card

    def _build_language_card(self) -> Card:
        card = Card()
        row = QHBoxLayout()
        body = QVBoxLayout()
        body.addWidget(self._h2(i18n.t("page.settings.section_language")))
        body.addWidget(QLabel(i18n.t("page.settings.language_label")))
        row.addLayout(body, stretch=1)
        self._lang_combo = QComboBox()
        for code, name in i18n.languages.items():
            self._lang_combo.addItem(name, userData=code)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        row.addWidget(self._lang_combo)
        card.layout().addLayout(row)
        return card

    def _build_theme_card(self) -> Card:
        card = Card()
        row = QHBoxLayout()
        body = QVBoxLayout()
        body.addWidget(self._h2(i18n.t("page.settings.section_theme")))
        title = QLabel(i18n.t("appearance"))
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        body.addWidget(title)
        hint = QLabel(i18n.t("appearance_hint"))
        hint.setStyleSheet("color: #9ba0ab;")
        body.addWidget(hint)
        row.addLayout(body, stretch=1)
        self._theme_combo = QComboBox()
        self._theme_combo.addItem(i18n.t("theme_dark"), userData="dark")
        self._theme_combo.addItem(i18n.t("theme_light"), userData="light")
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        row.addWidget(self._theme_combo)
        card.layout().addLayout(row)
        return card

    def _on_theme_changed(self, _index: int) -> None:
        name = self._theme_combo.currentData()
        if name:
            self._state.set_theme(name)

    def _build_updates_card(self) -> Card:
        card = Card()
        row = QHBoxLayout()
        body = QVBoxLayout()
        body.addWidget(self._h2(i18n.t("page.settings.section_updates")))
        body.addWidget(QLabel(i18n.t("page.settings.check_updates_label")))
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
        bg = s.background_mode if s.background_mode in self._bg_buttons else "off"
        self._bg_buttons[bg].setChecked(True)
        self._interval_spin.setValue(s.auto_interval_min)
        self._tray_start_toggle.setChecked(s.start_in_tray)
        self._recursive_toggle.setChecked(s.recursive_scan)
        self._pdf_toggle.setChecked(s.inspect_pdf_docx)
        self._patterns_count_label.setText(
            i18n.t("page.settings.patterns_count", n=len(profile.content_patterns))
        )
        # Language
        for i in range(self._lang_combo.count()):
            if self._lang_combo.itemData(i) == self._state.data.language:
                self._lang_combo.setCurrentIndex(i)
                break
        # Theme
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == self._state.data.theme:
                self._theme_combo.setCurrentIndex(i)
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

    def _set_bg_mode(self, mode: str) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        profile.settings.background_mode = mode
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
