"""Home page: Preview + Organize + Undo + last-run summary."""
from __future__ import annotations

import threading
from pathlib import Path

import os

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
    QPlainTextEdit, QVBoxLayout, QWidget,
)

from app.core.i18n import i18n
from app.core.organize import apply_plan, scan_folder, undo_last
from app.core.state import AppState
from app.ui.pages.base_page import BasePage, InfoBanner
from app.ui.theme import active_palette, palette_signal


class _Bridge(QObject):
    """Marshall worker thread events back onto the GUI thread."""
    log = Signal(str)
    progress = Signal(int, int)
    finished_preview = Signal(int, int)        # files, categories
    finished_organize = Signal(int, int, int)  # moved, errors, elapsed (s*10)


class HomePage(BasePage):
    def __init__(self, state: AppState, parent=None) -> None:
        self._state = state
        self._busy = False
        self._bridge = _Bridge()
        self._bridge.log.connect(self._append_log)
        self._bridge.progress.connect(self._set_progress)
        self._bridge.finished_preview.connect(self._on_preview_done)
        self._bridge.finished_organize.connect(self._on_organize_done)
        super().__init__(
            title=i18n.t("page_home_title"),
            subtitle=i18n.t("page_home_subtitle"),
            parent=parent,
        )
        state.folder_changed.connect(self._on_folder_changed)
        state.active_profile_changed.connect(self._update_profile_label)
        state.profiles_changed.connect(self._update_profile_label)
        self._update_profile_label()
        self._on_folder_changed(state.current_folder)

    # ----- layout -----

    def build_body(self, layout: QVBoxLayout) -> None:
        layout.addWidget(InfoBanner(i18n.t("page_home_banner")))

        meta = QHBoxLayout()
        self._profile_label = QLabel("")
        meta.addWidget(self._profile_label)
        meta.addStretch(1)
        self._folder_label = QLabel("No folder selected")
        meta.addWidget(self._folder_label)
        layout.addLayout(meta)
        self._restyle_meta()
        palette_signal().connect(self._restyle_meta)

        # Action buttons
        buttons = QHBoxLayout()
        self.preview_btn = QPushButton(i18n.t("preview_action"))
        self.preview_btn.setObjectName("primary")
        self.preview_btn.setCursor(Qt.PointingHandCursor)
        self.preview_btn.clicked.connect(self._preview)
        buttons.addWidget(self.preview_btn)

        self.organize_btn = QPushButton(i18n.t("organize_action"))
        self.organize_btn.setObjectName("secondary")
        self.organize_btn.setCursor(Qt.PointingHandCursor)
        self.organize_btn.clicked.connect(self._organize)
        buttons.addWidget(self.organize_btn)

        self.undo_btn = QPushButton(i18n.t("undo_action"))
        self.undo_btn.setObjectName("secondary")
        self.undo_btn.setCursor(Qt.PointingHandCursor)
        self.undo_btn.clicked.connect(self._undo)
        buttons.addWidget(self.undo_btn)

        self.open_explorer_btn = QPushButton("Open in Explorer")
        self.open_explorer_btn.setObjectName("secondary")
        self.open_explorer_btn.setCursor(Qt.PointingHandCursor)
        self.open_explorer_btn.setToolTip("Reveal the selected folder in Windows Explorer")
        self.open_explorer_btn.clicked.connect(self._open_in_explorer)
        buttons.addWidget(self.open_explorer_btn)

        buttons.addStretch(1)
        layout.addLayout(buttons)

        # Page-local shortcuts. Ctrl+P/O/Z only fire while the page is shown.
        for seq, slot in (
            ("Ctrl+P", self._preview),
            ("Ctrl+O", self._organize),
            ("Ctrl+Z", self._undo),
            ("F5", self._preview),
        ):
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        layout.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(280)
        layout.addWidget(self.log, stretch=1)

    # ----- state hooks -----

    def _update_profile_label(self) -> None:
        profile = self._state.active_profile()
        self._profile_label.setText(
            f"Profile: {profile.name}" if profile else "No profile")

    def _restyle_meta(self) -> None:
        p = active_palette()
        self._profile_label.setStyleSheet(
            f"color: {p.text}; font-weight: 600;")
        self._folder_label.setStyleSheet(f"color: {p.text_dim};")

    def _on_folder_changed(self, folder: Path | None) -> None:
        if folder:
            text = str(folder)
            if len(text) > 60:
                text = "..." + text[-58:]
            self._folder_label.setText(text)
        else:
            self._folder_label.setText("No folder selected")

    # ----- preview / organize / undo -----

    def _require_ready(self) -> Path | None:
        if self._busy:
            return None
        folder = self._state.current_folder
        if not folder or not folder.is_dir():
            QMessageBox.information(
                self, "Pick a folder",
                "Use the picker at the top right to choose a folder first.")
            return None
        if not self._state.active_profile():
            QMessageBox.warning(
                self, "No profile",
                "Create a profile from the Profiles tab.")
            return None
        return folder

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for btn in (self.preview_btn, self.organize_btn, self.undo_btn):
            btn.setEnabled(not busy)

    def _append_log(self, line: str) -> None:
        self.log.appendPlainText(line)

    def _set_progress(self, value: int, total: int) -> None:
        if total <= 0:
            self.progress.setRange(0, 0)  # busy indicator
        else:
            self.progress.setRange(0, total)
            self.progress.setValue(value)

    def _preview(self) -> None:
        folder = self._require_ready()
        if not folder:
            return
        self._set_busy(True)
        self.log.clear()
        self._append_log(f"=== Preview: {folder} ===")
        threading.Thread(
            target=self._preview_worker, args=(folder,), daemon=True,
        ).start()

    def _preview_worker(self, folder: Path) -> None:
        profile = self._state.active_profile()
        if not profile:
            return

        def progress(i: int, total: int, _name: str) -> None:
            self._bridge.progress.emit(i, total)

        try:
            plan = scan_folder(folder, profile, progress_cb=progress)
        except Exception as exc:  # noqa: BLE001
            self._bridge.log.emit(f"ERROR: {exc}")
            self._bridge.finished_preview.emit(0, 0)
            return

        self._state.last_plan = plan
        grouped: dict[str, list[str]] = {}
        lookup = {c.id: c.name for c in profile.categories}
        for m in plan:
            label = lookup.get(m.category_id, m.dst.parent.name or "Folder")
            grouped.setdefault(label, []).append(m.src.name)
        for label in sorted(grouped):
            self._bridge.log.emit(f"[{label}]  ({len(grouped[label])})")
            for name in sorted(grouped[label]):
                self._bridge.log.emit(f"  - {name}")
            self._bridge.log.emit("")
        self._bridge.finished_preview.emit(len(plan), len(grouped))

    def _on_preview_done(self, files: int, cats: int) -> None:
        self._append_log(f"Total: {files} files, {cats} categories.")
        self._set_busy(False)

    def _organize(self) -> None:
        folder = self._require_ready()
        if not folder:
            return
        if not self._state.last_plan:
            confirmed = QMessageBox.question(
                self, "No preview yet",
                "Run Preview first so you can see what will move. Run anyway?",
            )
            if confirmed != QMessageBox.Yes:
                return

        self._set_busy(True)
        self.log.clear()
        self._append_log(f"=== Organize: {folder} ===")
        threading.Thread(
            target=self._organize_worker, args=(folder,), daemon=True,
        ).start()

    def _organize_worker(self, folder: Path) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        plan = self._state.last_plan or scan_folder(folder, profile)

        def on_move(m):
            self._bridge.log.emit(f"  → {m.src.name}")

        def on_error(m, exc):
            self._bridge.log.emit(f"  ERROR: {m.src.name}: {exc}")

        result = apply_plan(folder, plan,
                            on_move=on_move, on_error=on_error)
        self._state.last_plan = []
        self._state.last_result = result
        self._bridge.finished_organize.emit(
            result.moved, result.errors,
            int(result.elapsed_seconds * 10),
        )

    def _on_organize_done(self, moved: int, errors: int,
                          elapsed_dec: int) -> None:
        secs = elapsed_dec / 10.0
        self._append_log("")
        self._append_log(
            f"Done. Moved {moved}, errors {errors}, {secs:.1f}s")
        self._set_busy(False)
        if self._state.last_result and self._state.last_result.moved:
            QMessageBox.information(
                self, "Organize complete",
                f"Moved {moved} file(s) in {secs:.1f}s\n"
                f"Errors: {errors}",
            )

    def _open_in_explorer(self) -> None:
        folder = self._state.current_folder
        if folder and folder.is_dir():
            try:
                os.startfile(str(folder))
            except OSError as exc:
                QMessageBox.warning(self, "Open folder", str(exc))
        else:
            QMessageBox.information(
                self, "Pick a folder",
                "Use the picker at the top right to choose a folder first.",
            )

    def _undo(self) -> None:
        folder = self._require_ready()
        if not folder:
            return
        confirm = QMessageBox.question(
            self, "Undo last run",
            f"Reverse the most recent organize on:\n{folder}",
        )
        if confirm != QMessageBox.Yes:
            return
        restored, errors = undo_last(folder)
        QMessageBox.information(
            self, "Undo complete",
            f"Restored {restored} file(s)\nErrors: {errors}",
        )
