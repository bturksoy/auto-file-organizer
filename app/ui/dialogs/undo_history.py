"""Browse the undo log of a folder and roll back operations."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,
)

from app.core.organize import UNDO_LOG_NAME, load_undo_log, undo_last


class UndoHistoryDialog(QDialog):
    """Shows every entry in `.file-organizer-undo.json` newest-first.

    The only action right now is "Undo last" — peeling off the newest
    entry. Undoing arbitrary middle entries is risky (subsequent
    operations may have re-touched the same files), so we surface the
    full history for context but only allow rolling back from the top.
    """

    def __init__(self, folder: Path, parent=None) -> None:
        super().__init__(parent)
        self._folder = folder
        self.setWindowTitle("Undo history")
        self.setMinimumSize(520, 360)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel(
            f"Past organize runs in <b>{folder.name}</b> (newest first)."
        ))

        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget { background: transparent; border: 1px solid #2c2e36;"
            " border-radius: 8px; padding: 4px; }"
            " QListWidget::item { padding: 8px 6px; }"
        )
        layout.addWidget(self._list, stretch=1)

        self._summary = QLabel("")
        self._summary.setStyleSheet("color: #9ba0ab;")
        layout.addWidget(self._summary)

        actions = QHBoxLayout()
        self._undo_btn = QPushButton("Undo latest")
        self._undo_btn.setObjectName("primary")
        self._undo_btn.setCursor(Qt.PointingHandCursor)
        self._undo_btn.clicked.connect(self._on_undo)
        actions.addWidget(self._undo_btn)

        self._clear_btn = QPushButton("Clear history")
        self._clear_btn.setObjectName("secondary")
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.setToolTip(
            "Delete the undo log file. Files are not affected.")
        self._clear_btn.clicked.connect(self._on_clear)
        actions.addWidget(self._clear_btn)

        actions.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.accept)
        actions.addWidget(buttons)
        layout.addLayout(actions)

        self._refresh()

    def _refresh(self) -> None:
        history = load_undo_log(self._folder)
        self._list.clear()
        for i, entry in enumerate(reversed(history)):
            ts = entry.get("timestamp", "?")
            moves = entry.get("moves", [])
            copies = sum(1 for m in moves if m.get("copy"))
            move_count = len(moves) - copies
            label_parts = []
            if move_count:
                label_parts.append(f"{move_count} moved")
            if copies:
                label_parts.append(f"{copies} copied")
            summary = ", ".join(label_parts) or "no operations"
            tag = " (latest)" if i == 0 else ""
            item = QListWidgetItem(f"{ts}  ·  {summary}{tag}")
            item.setData(Qt.UserRole, entry)
            self._list.addItem(item)

        self._summary.setText(
            f"{len(history)} entr{'y' if len(history) == 1 else 'ies'} on disk."
        )
        has_any = bool(history)
        self._undo_btn.setEnabled(has_any)
        self._clear_btn.setEnabled(has_any)

    def _on_undo(self) -> None:
        restored, errors = undo_last(self._folder)
        QMessageBox.information(
            self, "Undo",
            f"Restored {restored} file(s)\nErrors: {errors}",
        )
        self._refresh()

    def _on_clear(self) -> None:
        confirm = QMessageBox.question(
            self, "Clear history",
            "Delete the undo log? The files already on disk stay where they "
            "are; you just lose the ability to roll back from this dialog.",
        )
        if confirm != QMessageBox.Yes:
            return
        log = self._folder / UNDO_LOG_NAME
        try:
            log.unlink(missing_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "Clear history", str(exc))
        self._refresh()
