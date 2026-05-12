"""Duplicate-finder dialog.

Scans the current folder for byte-identical files, presents the groups
in a tree, and lets the user pick files to send to the recycle bin (or
permanently delete if send2trash is unavailable).
"""
from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QMessageBox, QProgressBar, QPushButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout,
)

from app.core.duplicates import (
    DuplicateGroup, find_duplicates, human_size,
)


try:
    from send2trash import send2trash  # type: ignore[import-untyped]
    _HAVE_TRASH = True
except Exception:  # pragma: no cover
    _HAVE_TRASH = False


class _Bridge(QObject):
    progress = Signal(int, int)
    finished = Signal(list)
    error = Signal(str)


class DuplicatesDialog(QDialog):
    def __init__(self, folder: Path, recursive: bool = False,
                 parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Find duplicates")
        self.setMinimumSize(820, 540)
        self._folder = folder
        self._recursive = recursive
        self._groups: list[DuplicateGroup] = []
        self._bridge = _Bridge()
        self._bridge.progress.connect(self._on_progress)
        self._bridge.finished.connect(self._on_finished)
        self._bridge.error.connect(self._on_error)

        outer = QVBoxLayout(self)

        head = QLabel(
            f"Scanning <b>{folder}</b> for byte-identical duplicate files."
        )
        head.setWordWrap(True)
        outer.addWidget(head)

        self._status = QLabel("Hashing candidates…")
        self._status.setStyleSheet("color: #9ba0ab;")
        outer.addWidget(self._status)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        outer.addWidget(self._progress)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(["Path", "Size", "Modified", "Wasted"])
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setUniformRowHeights(True)
        self._tree.setColumnWidth(0, 420)
        self._tree.setColumnWidth(1, 90)
        self._tree.setColumnWidth(2, 150)
        self._tree.setColumnWidth(3, 90)
        outer.addWidget(self._tree, stretch=1)

        action_row = QHBoxLayout()
        keep_btn = QPushButton("Keep oldest, mark rest")
        keep_btn.setToolTip(
            "Tick every duplicate except the oldest in each group")
        keep_btn.clicked.connect(self._mark_keep_oldest)
        action_row.addWidget(keep_btn)

        clear_btn = QPushButton("Clear ticks")
        clear_btn.clicked.connect(self._clear_ticks)
        action_row.addWidget(clear_btn)

        open_btn = QPushButton("Open in Explorer")
        open_btn.clicked.connect(self._open_selected_in_explorer)
        action_row.addWidget(open_btn)

        action_row.addStretch(1)
        self._delete_btn = QPushButton(
            "Send ticked to Recycle Bin" if _HAVE_TRASH
            else "Delete ticked files…"
        )
        self._delete_btn.setObjectName("primary")
        self._delete_btn.clicked.connect(self._delete_ticked)
        action_row.addWidget(self._delete_btn)
        outer.addLayout(action_row)

        if not _HAVE_TRASH:
            warn = QLabel(
                "send2trash is not installed; deletion will be permanent."
            )
            warn.setStyleSheet("color: #f7c469;")
            outer.addWidget(warn)

        close_box = QDialogButtonBox(QDialogButtonBox.Close)
        close_box.rejected.connect(self.reject)
        outer.addWidget(close_box)

        self._start_scan()

    # ----- scan -----------------------------------------------------------

    def _start_scan(self) -> None:
        self._tree.clear()
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self) -> None:
        try:
            groups = find_duplicates(
                self._folder, recursive=self._recursive,
                progress_cb=lambda i, total:
                    self._bridge.progress.emit(i, total),
            )
        except Exception as exc:  # noqa: BLE001
            self._bridge.error.emit(str(exc))
            return
        self._bridge.finished.emit(groups)

    def _on_progress(self, i: int, total: int) -> None:
        if total <= 0:
            self._progress.setRange(0, 0)
        else:
            self._progress.setRange(0, total)
            self._progress.setValue(i)
        self._status.setText(f"Hashing candidates ({i}/{total})…")

    def _on_finished(self, groups: list) -> None:
        self._groups = groups
        self._progress.setRange(0, 1)
        self._progress.setValue(1)
        self._populate_tree()
        total_wasted = sum(g.wasted_bytes for g in groups)
        if groups:
            self._status.setText(
                f"Found {len(groups)} group(s), "
                f"{sum(len(g.files) for g in groups)} duplicate file(s). "
                f"Reclaimable: {human_size(total_wasted)}."
            )
        else:
            self._status.setText("No duplicates found in this folder.")

    def _on_error(self, msg: str) -> None:
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._status.setText(f"Scan failed: {msg}")

    # ----- tree -----------------------------------------------------------

    def _populate_tree(self) -> None:
        self._tree.clear()
        for idx, group in enumerate(self._groups, start=1):
            parent = QTreeWidgetItem([
                f"Group {idx} — {len(group.files)} copies",
                human_size(group.size),
                "",
                human_size(group.wasted_bytes),
            ])
            parent.setFirstColumnSpanned(False)
            self._tree.addTopLevelItem(parent)
            parent.setExpanded(True)
            for f in group.files:
                child = QTreeWidgetItem([
                    str(f.path),
                    human_size(f.size),
                    datetime.fromtimestamp(f.mtime).strftime("%Y-%m-%d %H:%M"),
                    "",
                ])
                child.setCheckState(0, Qt.Unchecked)
                child.setData(0, Qt.UserRole, f.path)
                parent.addChild(child)

    def _iter_file_items(self):
        for i in range(self._tree.topLevelItemCount()):
            parent = self._tree.topLevelItem(i)
            for j in range(parent.childCount()):
                yield parent, parent.child(j), j

    def _mark_keep_oldest(self) -> None:
        # Children inside each parent are already in mtime-ascending order
        # because find_duplicates sorts that way; tick everything past
        # index 0.
        for parent, child, idx in self._iter_file_items():
            child.setCheckState(0, Qt.Checked if idx > 0 else Qt.Unchecked)

    def _clear_ticks(self) -> None:
        for _, child, _ in self._iter_file_items():
            child.setCheckState(0, Qt.Unchecked)

    def _ticked_paths(self) -> list[Path]:
        out: list[Path] = []
        for _, child, _ in self._iter_file_items():
            if child.checkState(0) == Qt.Checked:
                path = child.data(0, Qt.UserRole)
                if isinstance(path, Path):
                    out.append(path)
        return out

    # ----- actions --------------------------------------------------------

    def _open_selected_in_explorer(self) -> None:
        items = self._tree.selectedItems()
        if not items:
            return
        item = items[0]
        path = item.data(0, Qt.UserRole)
        if isinstance(path, Path) and path.exists():
            try:
                os.startfile(str(path.parent))
            except OSError as exc:
                QMessageBox.warning(self, "Open folder", str(exc))

    def _delete_ticked(self) -> None:
        paths = self._ticked_paths()
        if not paths:
            QMessageBox.information(
                self, "Nothing to delete",
                "Tick the duplicate files you want to remove first.")
            return
        verb = "Send to Recycle Bin" if _HAVE_TRASH else "PERMANENTLY DELETE"
        confirm = QMessageBox.question(
            self, "Confirm",
            f"{verb} {len(paths)} file(s)?",
        )
        if confirm != QMessageBox.Yes:
            return
        removed = 0
        errors = 0
        for path in paths:
            try:
                if _HAVE_TRASH:
                    send2trash(str(path))
                else:
                    path.unlink(missing_ok=True)
                removed += 1
            except Exception:  # noqa: BLE001
                errors += 1
        QMessageBox.information(
            self, "Done",
            f"Removed {removed} file(s). Errors: {errors}.\n"
            "Rescanning…",
        )
        self._start_scan()
