"""Home page: Preview + Organize + Undo + last-run summary."""
from __future__ import annotations

import threading
from pathlib import Path

import os

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QPlainTextEdit, QVBoxLayout, QWidget,
)

from app.core.i18n import i18n
from app.core.organize import apply_plan, scan_folder, undo_last
from app.core.state import AppState
from app.ui.dialogs.duplicates import DuplicatesDialog
from app.ui.dialogs.plan_editor import PlanEditorDialog
from app.ui.dialogs.stats import StatsDialog
from app.ui.dialogs.undo_history import UndoHistoryDialog
from app.ui.pages.base_page import BasePage, InfoBanner
from app.ui.theme import active_palette, palette_signal
from app.ui.widgets.organize_banner import OrganizeBanner, STATS_THRESHOLD


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

        self.open_explorer_btn = QPushButton(i18n.t("action.open_in_explorer"))
        self.open_explorer_btn.setObjectName("secondary")
        self.open_explorer_btn.setCursor(Qt.PointingHandCursor)
        self.open_explorer_btn.setToolTip(i18n.t("page.home.tooltip.open_in_explorer"))
        self.open_explorer_btn.clicked.connect(self._open_in_explorer)
        buttons.addWidget(self.open_explorer_btn)

        self.history_btn = QPushButton(i18n.t("page.home.history_btn"))
        self.history_btn.setObjectName("secondary")
        self.history_btn.setCursor(Qt.PointingHandCursor)
        self.history_btn.setToolTip(i18n.t("page.home.tooltip.history"))
        self.history_btn.clicked.connect(self._open_history)
        buttons.addWidget(self.history_btn)

        self.edit_plan_btn = QPushButton(i18n.t("page.home.edit_plan_btn"))
        self.edit_plan_btn.setObjectName("secondary")
        self.edit_plan_btn.setCursor(Qt.PointingHandCursor)
        self.edit_plan_btn.setToolTip(i18n.t("page.home.tooltip.edit_plan"))
        self.edit_plan_btn.setEnabled(False)
        self.edit_plan_btn.clicked.connect(self._open_plan_editor)
        buttons.addWidget(self.edit_plan_btn)

        self.duplicates_btn = QPushButton(i18n.t("page.home.find_duplicates_btn"))
        self.duplicates_btn.setObjectName("secondary")
        self.duplicates_btn.setCursor(Qt.PointingHandCursor)
        self.duplicates_btn.setToolTip(i18n.t("page.home.tooltip.find_duplicates"))
        self.duplicates_btn.clicked.connect(self._open_duplicates)
        buttons.addWidget(self.duplicates_btn)

        buttons.addStretch(1)
        layout.addLayout(buttons)

        # Search filter for the log content.
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel(i18n.t("common.filter_label")))
        self._log_filter = QLineEdit()
        self._log_filter.setPlaceholderText(i18n.t("page.home.placeholder.log_filter"))
        self._log_filter.textChanged.connect(self._apply_log_filter)
        filter_row.addWidget(self._log_filter, stretch=1)
        layout.addLayout(filter_row)

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

        # Inline result banner — hidden until an organize run completes.
        self._result_banner = OrganizeBanner()
        self._result_banner.stats_requested.connect(self._show_stats_dialog)
        layout.addWidget(self._result_banner)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(280)
        layout.addWidget(self.log, stretch=1)
        # Master copy of log lines so the filter can re-render without
        # losing the original output.
        self._log_lines: list[str] = []

    # ----- state hooks -----

    def _update_profile_label(self) -> None:
        profile = self._state.active_profile()
        if profile:
            self._profile_label.setText(
                i18n.t("page.home.profile_label", name=profile.name))
        else:
            self._profile_label.setText(i18n.t("page.home.no_profile"))

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
            self._folder_label.setText(i18n.t("page.home.no_folder_selected"))

    # ----- preview / organize / undo -----

    def _require_ready(self) -> Path | None:
        if self._busy:
            return None
        folder = self._state.current_folder
        if not folder or not folder.is_dir():
            QMessageBox.information(
                self, i18n.t("dialog.pick_folder.title"),
                i18n.t("dialog.pick_folder.body"))
            return None
        if not self._state.active_profile():
            QMessageBox.warning(
                self, i18n.t("dialog.no_profile.title"),
                i18n.t("dialog.no_profile.body"))
            return None
        return folder

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for btn in (self.preview_btn, self.organize_btn, self.undo_btn):
            btn.setEnabled(not busy)

    def _append_log(self, line: str) -> None:
        self._log_lines.append(line)
        needle = self._log_filter.text().strip().lower()
        # Always show category headers + summary lines; only filter file rows.
        is_file_row = line.startswith("  - ")
        if not needle or (not is_file_row) or needle in line.lower():
            self.log.appendPlainText(line)

    def _apply_log_filter(self, _text: str) -> None:
        needle = self._log_filter.text().strip().lower()
        self.log.clear()
        for line in self._log_lines:
            is_file_row = line.startswith("  - ")
            if not needle or (not is_file_row) or needle in line.lower():
                self.log.appendPlainText(line)
        self.log.moveCursor(QTextCursor.Start)

    def _open_plan_editor(self) -> None:
        plan = self._state.last_plan
        profile = self._state.active_profile()
        if not plan or not profile:
            return
        dlg = PlanEditorDialog(plan, profile, parent=self)
        # Re-render the log once the user closes the editor — counts may
        # have shifted and reassignments changed category groupings.
        dlg.plan_changed.connect(lambda: self._render_plan_log())
        dlg.exec()
        self._render_plan_log()

    def _render_plan_log(self) -> None:
        plan = self._state.last_plan
        profile = self._state.active_profile()
        if not plan or not profile:
            return
        lookup = {c.id: c.name for c in profile.categories}
        grouped: dict[str, list[str]] = {}
        for m in plan:
            label = lookup.get(m.category_id, m.dst.parent.name or "Folder")
            grouped.setdefault(label, []).append(m.src.name)
        self._log_lines = []
        for label in sorted(grouped):
            self._log_lines.append(f"[{label}]  ({len(grouped[label])})")
            for name in sorted(grouped[label]):
                self._log_lines.append(f"  - {name}")
            self._log_lines.append("")
        self._log_lines.append(
            f"Total: {len(plan)} files, {len(grouped)} categories.")
        self._apply_log_filter("")

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
        self._log_lines.clear()
        self.log.clear()
        self._append_log(i18n.t("page.home.preview_log_header", path=str(folder)))
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
        # Enable Edit plan now that we have a fresh plan in state.
        self.edit_plan_btn.setEnabled(bool(plan))
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
                self, i18n.t("dialog.no_preview.title"),
                i18n.t("dialog.no_preview.body"),
            )
            if confirmed != QMessageBox.Yes:
                return

        self._set_busy(True)
        self._result_banner.hide_result()
        self._log_lines.clear()
        self.log.clear()
        self._append_log(i18n.t("page.home.organize_log_header", path=str(folder)))
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
        self._append_log(i18n.t(
            "page.home.organize_done_summary",
            moved=moved, errors=errors, secs=secs))
        self._set_busy(False)

        result = self._state.last_result
        cats_touched = len(result.per_category) if result else 0
        self._result_banner.show_result(moved, errors, cats_touched)

        # The full stats popup is now reserved for sizable moves where the
        # per-category breakdown is genuinely useful. Smaller runs are
        # covered by the inline banner; users can still open the popup
        # from the banner's "View stats" button.
        if result and result.moved >= STATS_THRESHOLD:
            self._show_stats_dialog()

    def _show_stats_dialog(self) -> None:
        result = self._state.last_result
        if not result:
            return
        profile = self._state.active_profile()
        lookup = None
        if profile:
            names = {c.id: c.name for c in profile.categories}
            lookup = names.get
        StatsDialog(result, category_lookup=lookup, parent=self).exec()

    def _open_duplicates(self) -> None:
        folder = self._state.current_folder
        if not folder or not folder.is_dir():
            QMessageBox.information(
                self, i18n.t("dialog.pick_folder.title"),
                i18n.t("dialog.pick_folder.body_duplicates"))
            return
        profile = self._state.active_profile()
        recursive = bool(profile and profile.settings.recursive_scan)
        DuplicatesDialog(folder, recursive=recursive, parent=self).exec()

    def _open_history(self) -> None:
        folder = self._state.current_folder
        if not folder or not folder.is_dir():
            QMessageBox.information(
                self, i18n.t("dialog.pick_folder.title"),
                i18n.t("dialog.pick_folder.body_history"),
            )
            return
        UndoHistoryDialog(folder, parent=self).exec()

    def _open_in_explorer(self) -> None:
        folder = self._state.current_folder
        if folder and folder.is_dir():
            try:
                os.startfile(str(folder))
            except OSError as exc:
                QMessageBox.warning(self, i18n.t("dialog.open_folder.title"), str(exc))
        else:
            QMessageBox.information(
                self, i18n.t("dialog.pick_folder.title"),
                i18n.t("dialog.pick_folder.body"),
            )

    def _undo(self) -> None:
        folder = self._require_ready()
        if not folder:
            return
        confirm = QMessageBox.question(
            self, i18n.t("dialog.undo_last.title"),
            i18n.t("dialog.undo_last.body", folder=folder),
        )
        if confirm != QMessageBox.Yes:
            return
        restored, errors = undo_last(folder)
        # Toast instead of modal popup — undo is low-risk to confirm.
        toaster = self._toast_manager()
        if toaster is not None:
            if errors:
                toaster.warning(i18n.t(
                    "toast.undo_with_errors",
                    restored=restored, errors=errors))
            else:
                toaster.success(i18n.t("toast.undo_done", restored=restored))
        # If for some reason the toast host isn't available, fall back to
        # the old behaviour so the user still gets feedback.
        else:
            QMessageBox.information(
                self, i18n.t("dialog.undo_complete.title"),
                i18n.t("dialog.undo_complete.body",
                       restored=restored, errors=errors),
            )

    def _toast_manager(self):
        """Find the MainWindow's ToastManager if one is attached."""
        return getattr(self.window(), "toast_manager", None)
