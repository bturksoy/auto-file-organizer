"""Top-level QMainWindow: sidebar + top bar + stacked pages."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

from app.core.state import AppState
from app.ui.pages.categories import CategoriesPage
from app.ui.pages.folders import FoldersPage
from app.ui.pages.home import HomePage
from app.ui.pages.profiles import ProfilesPage
from app.ui.pages.rules import RulesPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.sidebar import Sidebar


class MainWindow(QMainWindow):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self._state = state
        self.setWindowTitle("Auto File Organizer")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)
        self.setAcceptDrops(True)
        self._build()
        self._build_statusbar()
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

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topBar")
        bar.setFixedHeight(56)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 10, 18, 10)

        breadcrumb = QLabel("→  Auto File Organizer")
        breadcrumb.setObjectName("topBarTitle")
        layout.addWidget(breadcrumb)
        layout.addStretch(1)

        self.folder_button = QPushButton("\U0001F4C1  Pick folder…")
        self.folder_button.setObjectName("folderPicker")
        self.folder_button.setCursor(Qt.PointingHandCursor)
        self.folder_button.setToolTip(
            "Choose a folder to scan. You can also drag and drop one anywhere "
            "in this window.")
        self.folder_button.clicked.connect(self._pick_folder)
        layout.addWidget(self.folder_button)
        return bar

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
            self._status_profile.setText(f"Profile: {profile.name}")
            mode = profile.settings.organization_mode.replace("_", " ")
            self._status_mode.setText(f"Mode: {mode}")
        else:
            self._status_profile.setText("No profile")
            self._status_mode.setText("")

    def _on_nav(self, key: str) -> None:
        page = self._pages.get(key)
        if page is not None:
            self._stack.setCurrentWidget(page)

    def _pick_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Select folder")
        if chosen:
            self._state.set_folder(Path(chosen))

    def _on_folder_changed(self, folder: Path | None) -> None:
        if not folder:
            self.folder_button.setText("\U0001F4C1  Pick folder…")
            self._status_folder.setText("No folder")
            return
        path_str = str(folder)
        display = "…" + path_str[-46:] if len(path_str) > 48 else path_str
        self.folder_button.setText(f"\U0001F4C1  {display}")
        self._status_folder.setText(path_str)
