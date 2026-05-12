"""Top-level QMainWindow: sidebar + top bar + stacked pages."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
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
        self._build()
        self._state.folder_changed.connect(self._on_folder_changed)
        self._on_folder_changed(self._state.current_folder)

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
        self.folder_button.clicked.connect(self._pick_folder)
        layout.addWidget(self.folder_button)
        return bar

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
            return
        path_str = str(folder)
        if len(path_str) > 48:
            path_str = "…" + path_str[-46:]
        self.folder_button.setText(f"\U0001F4C1  {path_str}")
