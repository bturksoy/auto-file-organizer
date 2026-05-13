"""Browse the undo log of a folder and roll back operations."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,
)

from app.core.i18n import i18n
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
        self.setWindowTitle(i18n.t("dialog.undo_history.title"))
        self.setMinimumSize(520, 360)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel(
            i18n.t("dialog.undo_history.intro", folder=folder.name)
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
        self._undo_btn = QPushButton(i18n.t("dialog.undo_history.undo_btn"))
        self._undo_btn.setObjectName("primary")
        self._undo_btn.setCursor(Qt.PointingHandCursor)
        self._undo_btn.clicked.connect(self._on_undo)
        actions.addWidget(self._undo_btn)

        self._clear_btn = QPushButton(i18n.t("dialog.undo_history.clear_btn"))
        self._clear_btn.setObjectName("secondary")
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.setToolTip(i18n.t("dialog.undo_history.tooltip.clear"))
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
                label_parts.append(
                    i18n.t("dialog.undo_history.moved", n=move_count))
            if copies:
                label_parts.append(
                    i18n.t("dialog.undo_history.copied", n=copies))
            summary = ", ".join(label_parts) or i18n.t("dialog.undo_history.no_ops")
            tag = i18n.t("dialog.undo_history.latest_tag") if i == 0 else ""
            item = QListWidgetItem(f"{ts}  ·  {summary}{tag}")
            item.setData(Qt.UserRole, entry)
            self._list.addItem(item)

        self._summary.setText(
            i18n.t("dialog.undo_history.count", n=len(history))
        )
        has_any = bool(history)
        self._undo_btn.setEnabled(has_any)
        self._clear_btn.setEnabled(has_any)

    def _on_undo(self) -> None:
        restored, errors = undo_last(self._folder)
        QMessageBox.information(
            self, i18n.t("dialog.undo.title"),
            i18n.t("dialog.undo_complete.body",
                   restored=restored, errors=errors),
        )
        self._refresh()

    def _on_clear(self) -> None:
        confirm = QMessageBox.question(
            self, i18n.t("dialog.undo_history.clear_title"),
            i18n.t("dialog.undo_history.clear_body"),
        )
        if confirm != QMessageBox.Yes:
            return
        log = self._folder / UNDO_LOG_NAME
        try:
            log.unlink(missing_ok=True)
        except OSError as exc:
            QMessageBox.warning(
                self, i18n.t("dialog.undo_history.clear_title"), str(exc))
        self._refresh()
