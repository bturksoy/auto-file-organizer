"""Top-level QMainWindow: sidebar + top bar + stacked pages."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

from app.core.i18n import i18n
from app.core.state import AppState
from app.services.updates import APP_VERSION
from app.ui.dialogs.about import AboutDialog
from app.ui.pages.categories import CategoriesPage
from app.ui.pages.folders import FoldersPage
from app.ui.pages.home import HomePage
from app.ui.pages.profiles import ProfilesPage
from app.ui.pages.rules import RulesPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.sidebar import Sidebar
from app.ui.widgets.toast import ToastManager


class MainWindow(QMainWindow):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self._state = state
        self.setWindowTitle(i18n.t("sidebar.app_title"))
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)
        self.setAcceptDrops(True)
        self._build()
        self._build_statusbar()
        # ToastManager is attached after _build so toasts can find a sized
        # widget and place themselves correctly on first show.
        self.toast_manager = ToastManager.attach(self)
        self._state.folder_changed.connect(self._on_folder_changed)
        self._state.active_profile_changed.connect(self._refresh_status)
        self._state.profiles_changed.connect(self._refresh_status)
        self._on_folder_changed(self._state.current_folder)
        self._refresh_status()

    # ----- drag and drop a folder -----------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if not local:
                continue
            target = Path(local)
            if not target.is_dir():
                target = target.parent
            if target.is_dir():
                self._state.set_folder(target)
                event.acceptProposedAction()
                return

    def _build(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.sidebar = Sidebar()
        outer.addWidget(self.sidebar)

        content_holder = QWidget()
        content_holder.setObjectName("contentArea")
        content_layout = QVBoxLayout(content_holder)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        content_layout.addWidget(self._build_top_bar())

        self._stack = QStackedWidget()
        self._pages = {
            "home": HomePage(self._state),
            "folders": FoldersPage(self._state),
            "rules": RulesPage(self._state),
            "categories": CategoriesPage(self._state),
            "profiles": ProfilesPage(self._state),
            "settings": SettingsPage(self._state),
        }
        for page in self._pages.values():
            self._stack.addWidget(page)
        content_layout.addWidget(self._stack)

        outer.addWidget(content_holder, stretch=1)

        self.sidebar.selected.connect(self._on_nav)
        self.sidebar.select("home")

        self._install_shortcuts()

    # ----- keyboard shortcuts -----------------------------------------------

    def _install_shortcuts(self) -> None:
        """Page-switch shortcuts (Ctrl+1..6), Help (F1), and theme toggle."""
        nav_keys = [
            ("Ctrl+1", "home"),
            ("Ctrl+2", "folders"),
            ("Ctrl+3", "rules"),
            ("Ctrl+4", "categories"),
            ("Ctrl+5", "profiles"),
            ("Ctrl+6", "settings"),
        ]
        for seq, key in nav_keys:
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(lambda k=key: self.sidebar.select(k))

        about_sc = QShortcut(QKeySequence("F1"), self)
        about_sc.activated.connect(self._show_about)

        theme_sc = QShortcut(QKeySequence("Ctrl+T"), self)
        theme_sc.activated.connect(self._toggle_theme)

    def _toggle_theme(self) -> None:
        current = self._state.data.theme
        self._state.set_theme("light" if current == "dark" else "dark")

    def _show_about(self) -> None:
        # Resolve the bundled icon path so the dialog can show a large preview.
        from app.core.utils import resources_dir
        png = resources_dir() / "icon.png"
        AboutDialog(
            icon_path=str(png) if png.is_file() else None,
            version=APP_VERSION,
            parent=self,
        ).exec()

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topBar")
        bar.setFixedHeight(56)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 10, 18, 10)
        layout.setSpacing(8)

        breadcrumb = QLabel(i18n.t("topbar.breadcrumb"))
        breadcrumb.setObjectName("topBarTitle")
        layout.addWidget(breadcrumb)
        layout.addStretch(1)

        self._theme_button = QPushButton()
        self._theme_button.setObjectName("iconBtn")
        self._theme_button.setFixedSize(34, 34)
        self._theme_button.setCursor(Qt.PointingHandCursor)
        self._theme_button.setToolTip(i18n.t("topbar.tooltip.theme_toggle"))
        self._theme_button.clicked.connect(self._toggle_theme)
        self._refresh_theme_button_glyph()
        layout.addWidget(self._theme_button)

        self.folder_button = QPushButton("\U0001F4C1 " + i18n.t("topbar.pick_folder"))
        self.folder_button.setObjectName("folderPicker")
        self.folder_button.setCursor(Qt.PointingHandCursor)
        self.folder_button.setToolTip(i18n.t("topbar.tooltip.pick_folder"))
        self.folder_button.clicked.connect(self._pick_folder)
        layout.addWidget(self.folder_button)
        self._state.theme_changed.connect(
            lambda _: self._refresh_theme_button_glyph())
        return bar

    def _refresh_theme_button_glyph(self) -> None:
        """Show a sun while in dark mode (so the user 'goes light') and a moon
        otherwise. Keeps the same button slot regardless of theme state."""
        glyph = "☀" if self._state.data.theme == "dark" else "☾"
        self._theme_button.setText(glyph)

    def _build_statusbar(self) -> None:
        # All colors come from the active QSS stylesheet.
        bar = QStatusBar()
        self._status_profile = QLabel("")
        self._status_folder = QLabel("")
        self._status_mode = QLabel("")
        for lbl in (self._status_profile, self._status_mode,
                    self._status_folder):
            lbl.setContentsMargins(12, 0, 12, 0)
        bar.addWidget(self._status_profile)
        bar.addWidget(self._status_mode)
        bar.addPermanentWidget(self._status_folder)
        self.setStatusBar(bar)

    def _refresh_status(self) -> None:
        profile = self._state.active_profile()
        if profile:
            self._status_profile.setText(
                i18n.t("statusbar.profile", name=profile.name))
            mode_label = i18n.t(
                f"settings.org_mode.{profile.settings.organization_mode}.label")
            self._status_mode.setText(
                i18n.t("statusbar.mode", mode=mode_label))
        else:
            self._status_profile.setText(i18n.t("statusbar.no_profile"))
            self._status_mode.setText("")

    def _on_nav(self, key: str) -> None:
        # The sidebar emits page keys and a couple of action keys (About).
        # Action keys aren't in the stack, so route them separately.
        if key == "about":
            self._show_about()
            return
        page = self._pages.get(key)
        if page is not None:
            self._stack.setCurrentWidget(page)

    def _pick_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, i18n.t("dialog.pick_folder.caption"))
        if chosen:
            self._state.set_folder(Path(chosen))

    def _on_folder_changed(self, folder: Path | None) -> None:
        if not folder:
            self.folder_button.setText(
                "\U0001F4C1 " + i18n.t("topbar.pick_folder"))
            self._status_folder.setText(i18n.t("statusbar.no_folder"))
            return
        path_str = str(folder)
        display = "…" + path_str[-46:] if len(path_str) > 48 else path_str
        self.folder_button.setText(f"\U0001F4C1  {display}")
        self._status_folder.setText(path_str)
