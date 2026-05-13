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
from app.core.i18n import i18n


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
        self.setWindowTitle(i18n.t("dialog.duplicates.title"))
        self.setMinimumSize(820, 540)
        self._folder = folder
        self._recursive = recursive
        self._groups: list[DuplicateGroup] = []
        self._bridge = _Bridge()
        self._bridge.progress.connect(self._on_progress)
        self._bridge.finished.connect(self._on_finished)
        self._bridge.error.connect(self._on_error)

        outer = QVBoxLayout(self)

        head = QLabel(i18n.t("dialog.duplicates.header", folder=str(folder)))
        head.setWordWrap(True)
        outer.addWidget(head)

        self._status = QLabel(i18n.t("dialog.duplicates.status.initial"))
        self._status.setStyleSheet("color: #9ba0ab;")
        outer.addWidget(self._status)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        outer.addWidget(self._progress)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels([
            i18n.t("dialog.duplicates.col.path"),
            i18n.t("dialog.duplicates.col.size"),
            i18n.t("dialog.duplicates.col.modified"),
            i18n.t("dialog.duplicates.col.wasted"),
        ])
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setUniformRowHeights(True)
        self._tree.setColumnWidth(0, 420)
        self._tree.setColumnWidth(1, 90)
        self._tree.setColumnWidth(2, 150)
        self._tree.setColumnWidth(3, 90)
        outer.addWidget(self._tree, stretch=1)

        action_row = QHBoxLayout()
        keep_btn = QPushButton(i18n.t("dialog.duplicates.keep_oldest_btn"))
        keep_btn.setToolTip(i18n.t("dialog.duplicates.tooltip.keep_oldest"))
        keep_btn.clicked.connect(self._mark_keep_oldest)
        action_row.addWidget(keep_btn)

        clear_btn = QPushButton(i18n.t("dialog.duplicates.clear_ticks_btn"))
        clear_btn.clicked.connect(self._clear_ticks)
        action_row.addWidget(clear_btn)

        open_btn = QPushButton(i18n.t("action.open_in_explorer"))
        open_btn.clicked.connect(self._open_selected_in_explorer)
        action_row.addWidget(open_btn)

        action_row.addStretch(1)
        self._delete_btn = QPushButton(i18n.t(
            "dialog.duplicates.delete_btn.trash" if _HAVE_TRASH
            else "dialog.duplicates.delete_btn.perm"
        ))
        self._delete_btn.setObjectName("primary")
        self._delete_btn.clicked.connect(self._delete_ticked)
        action_row.addWidget(self._delete_btn)
        outer.addLayout(action_row)

        if not _HAVE_TRASH:
            warn = QLabel(i18n.t("dialog.duplicates.warn_no_trash"))
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
        self._status.setText(
            i18n.t("dialog.duplicates.status.hashing", i=i, total=total))

    def _on_finished(self, groups: list) -> None:
        self._groups = groups
        self._progress.setRange(0, 1)
        self._progress.setValue(1)
        self._populate_tree()
        total_wasted = sum(g.wasted_bytes for g in groups)
        if groups:
            self._status.setText(i18n.t(
                "dialog.duplicates.status.found",
                n=len(groups),
                f=sum(len(g.files) for g in groups),
                size=human_size(total_wasted),
            ))
        else:
            self._status.setText(i18n.t("dialog.duplicates.status.none"))

    def _on_error(self, msg: str) -> None:
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._status.setText(
            i18n.t("dialog.duplicates.status.failed", msg=msg))

    # ----- tree -----------------------------------------------------------

    def _populate_tree(self) -> None:
        self._tree.clear()
        for idx, group in enumerate(self._groups, start=1):
            parent = QTreeWidgetItem([
                i18n.t("dialog.duplicates.group_label",
                       idx=idx, count=len(group.files)),
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
                QMessageBox.warning(
                    self, i18n.t("dialog.open_folder.title"), str(exc))

    def _delete_ticked(self) -> None:
        paths = self._ticked_paths()
        if not paths:
            QMessageBox.information(
                self, i18n.t("dialog.duplicates.nothing_title"),
                i18n.t("dialog.duplicates.nothing_body"))
            return
        # Whole-sentence confirms keep translators free to reorder words.
        msg = i18n.t(
            "dialog.duplicates.confirm_trash" if _HAVE_TRASH
            else "dialog.duplicates.confirm_perm",
            n=len(paths),
        )
        confirm = QMessageBox.question(
            self, i18n.t("dialog.confirm.title"), msg,
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
            self, i18n.t("dialog.duplicates.done.title"),
            i18n.t("dialog.duplicates.done.body",
                   removed=removed, errors=errors),
        )
        self._start_scan()
