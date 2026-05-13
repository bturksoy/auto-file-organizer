"""First-run welcome wizard.

Shown once on the very first launch. Walks the user through:

  1. Welcome  — what the app does
  2. Folder   — suggest Downloads, let them pick anything
  3. Preview  — run a non-destructive scan, show the count
  4. Done     — offer to enable real-time watch + reveal the main window

Once the wizard exits (either via Finish or Skip), `state.data.first_run_seen`
flips to True so it never re-opens. Users who want to re-run it can clear
the flag from Settings; we don't surface that in the UI yet.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
    QWidget, QWizard, QWizardPage,
)

from app.core.i18n import i18n
from app.core.organize import scan_folder
from app.core.state import AppState
from app.ui.theme import active_palette, palette_signal


def _downloads_folder() -> Path | None:
    """Best-effort guess at the user's Downloads folder."""
    candidates = []
    home = os.environ.get("USERPROFILE") or str(Path.home())
    if home:
        candidates.append(Path(home) / "Downloads")
    for p in candidates:
        if p.is_dir():
            return p
    return None


class _Hero(QLabel):
    """Big heading text used at the top of each wizard page."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setWordWrap(True)
        self._restyle()
        palette_signal().connect(self._restyle)

    def _restyle(self) -> None:
        p = active_palette()
        self.setStyleSheet(
            f"color: {p.text}; font-size: 18px; font-weight: 600;")


class _Body(QLabel):
    """Body text under the hero — long descriptions or hints."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setWordWrap(True)
        self._restyle()
        palette_signal().connect(self._restyle)

    def _restyle(self) -> None:
        p = active_palette()
        self.setStyleSheet(f"color: {p.text_dim}; font-size: 13px;")


class _ScanBridge(QObject):
    """Marshalls scan results from the worker thread back to the GUI."""

    done = Signal(int, int)   # files_count, categories_count
    failed = Signal(str)


class WelcomePage(QWizardPage):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle(i18n.t("wizard.welcome.title"))
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(_Hero(i18n.t("wizard.welcome.hero")))
        layout.addWidget(_Body(i18n.t("wizard.welcome.body")))
        layout.addStretch(1)


class FolderPage(QWizardPage):
    folder_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle(i18n.t("wizard.folder.title"))
        self._folder: Path | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(_Hero(i18n.t("wizard.folder.hero")))
        layout.addWidget(_Body(i18n.t("wizard.folder.body")))

        row = QHBoxLayout()
        self._chosen_label = QLabel(i18n.t("wizard.folder.no_pick"))
        self._chosen_label.setWordWrap(True)
        row.addWidget(self._chosen_label, stretch=1)
        pick = QPushButton(i18n.t("action.browse"))
        pick.setObjectName("primary")
        pick.setCursor(Qt.PointingHandCursor)
        pick.clicked.connect(self._pick)
        row.addWidget(pick)
        layout.addLayout(row)

        # Optional one-tap suggestion when Downloads exists.
        downloads = _downloads_folder()
        if downloads is not None:
            suggest = QPushButton(i18n.t(
                "wizard.folder.suggest_downloads", path=str(downloads)))
            suggest.setObjectName("secondary")
            suggest.setCursor(Qt.PointingHandCursor)
            suggest.clicked.connect(lambda: self._set_folder(downloads))
            layout.addWidget(suggest)

        layout.addStretch(1)

    def _pick(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, i18n.t("dialog.pick_folder.caption"))
        if chosen:
            self._set_folder(Path(chosen))

    def _set_folder(self, path: Path) -> None:
        self._folder = path
        # Trim long paths so the label doesn't blow up the dialog width.
        text = str(path)
        if len(text) > 60:
            text = "…" + text[-58:]
        self._chosen_label.setText(text)
        self.folder_changed.emit()
        self.completeChanged.emit()

    def folder(self) -> Path | None:
        return self._folder

    def isComplete(self) -> bool:  # noqa: N802
        return self._folder is not None and self._folder.is_dir()


class PreviewPage(QWizardPage):
    """Runs a non-destructive scan against the picked folder and shows
    a one-line summary. No files move — that's still on the Home page."""

    def __init__(self, state: AppState, folder_page: FolderPage,
                 parent=None) -> None:
        super().__init__(parent)
        self.setTitle(i18n.t("wizard.preview.title"))
        self._state = state
        self._folder_page = folder_page
        self._bridge = _ScanBridge()
        self._bridge.done.connect(self._on_done)
        self._bridge.failed.connect(self._on_failed)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(_Hero(i18n.t("wizard.preview.hero")))
        self._status = _Body(i18n.t("wizard.preview.scanning"))
        layout.addWidget(self._status)
        layout.addStretch(1)

    def initializePage(self) -> None:  # noqa: N802
        folder = self._folder_page.folder()
        if folder is None:
            return
        self._status.setText(i18n.t("wizard.preview.scanning"))
        threading.Thread(
            target=self._scan_worker, args=(folder,), daemon=True,
        ).start()

    def _scan_worker(self, folder: Path) -> None:
        profile = self._state.active_profile()
        if profile is None:
            self._bridge.failed.emit("no profile")
            return
        try:
            plan = scan_folder(folder, profile)
        except Exception as exc:  # noqa: BLE001
            self._bridge.failed.emit(str(exc))
            return
        cat_ids = {m.category_id for m in plan}
        self._bridge.done.emit(len(plan), len(cat_ids))

    def _on_done(self, files: int, cats: int) -> None:
        if files == 0:
            self._status.setText(i18n.t("wizard.preview.empty"))
        else:
            self._status.setText(i18n.t(
                "wizard.preview.summary", files=files, categories=cats))

    def _on_failed(self, msg: str) -> None:
        self._status.setText(i18n.t("wizard.preview.failed", err=msg))


class DonePage(QWizardPage):
    """Offers the real-time toggle and remembers which folder the user picked."""

    def __init__(self, state: AppState, folder_page: FolderPage,
                 parent=None) -> None:
        super().__init__(parent)
        self.setTitle(i18n.t("wizard.done.title"))
        self._state = state
        self._folder_page = folder_page

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(_Hero(i18n.t("wizard.done.hero")))
        layout.addWidget(_Body(i18n.t("wizard.done.body")))

        self._realtime_btn = QPushButton(i18n.t("wizard.done.enable_realtime"))
        self._realtime_btn.setObjectName("primary")
        self._realtime_btn.setCursor(Qt.PointingHandCursor)
        self._realtime_btn.setCheckable(True)
        layout.addWidget(self._realtime_btn)

        hint = _Body(i18n.t("wizard.done.realtime_hint"))
        layout.addWidget(hint)
        layout.addStretch(1)

    def realtime_enabled(self) -> bool:
        return self._realtime_btn.isChecked()


class FirstRunWizard(QWizard):
    """Top-level wizard. Caller invokes `exec()` and reads `result()`."""

    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self._state = state
        self.setWindowTitle(i18n.t("wizard.window_title"))
        # Hide the side-image area and use a flat layout that matches our
        # dark theme. Qt's default Aero / Classic styles fight our QSS.
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.setOption(QWizard.NoCancelButtonOnLastPage, True)
        self.setOption(QWizard.HaveCustomButton1, True)
        self.setButtonText(QWizard.CustomButton1, i18n.t("wizard.skip_btn"))
        self.setButtonLayout([
            QWizard.CustomButton1,
            QWizard.Stretch,
            QWizard.BackButton,
            QWizard.NextButton,
            QWizard.FinishButton,
        ])
        self.customButtonClicked.connect(self._on_custom)
        self.setMinimumSize(560, 380)

        self._welcome = WelcomePage()
        self._folder = FolderPage()
        self._preview = PreviewPage(state, self._folder)
        self._done = DonePage(state, self._folder)

        for page in (self._welcome, self._folder, self._preview, self._done):
            self.addPage(page)

    def _on_custom(self, which: int) -> None:
        if which == QWizard.CustomButton1:
            # Treat Skip the same as cancelling — the run still counts as
            # "seen" from main.py's perspective.
            self.reject()

    def selected_folder(self) -> Path | None:
        return self._folder.folder()

    def realtime_requested(self) -> bool:
        return self._done.realtime_enabled()
