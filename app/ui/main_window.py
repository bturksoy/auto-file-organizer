"""Top-level QMainWindow: sidebar + top folder picker + stacked pages."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from app.ui.pages.categories import CategoriesPage
from app.ui.pages.folders import FoldersPage
from app.ui.pages.home import HomePage
from app.ui.pages.profiles import ProfilesPage
from app.ui.pages.rules import RulesPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.sidebar import Sidebar


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Auto File Organizer")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)

        self._current_folder: Path | None = None
        self._build()

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
            "home": HomePage(),
            "folders": FoldersPage(),
            "rules": RulesPage(),
            "categories": CategoriesPage(),
            "profiles": ProfilesPage(),
            "settings": SettingsPage(),
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
            self._current_folder = Path(chosen)
            self._refresh_folder_button()

    def _refresh_folder_button(self) -> None:
        if not self._current_folder:
            self.folder_button.setText("\U0001F4C1  Pick folder…")
            return
        # Truncate long paths from the left for readability.
        path_str = str(self._current_folder)
        if len(path_str) > 48:
            path_str = "…" + path_str[-46:]
        self.folder_button.setText(f"\U0001F4C1  {path_str}")
