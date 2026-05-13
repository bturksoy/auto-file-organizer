"""Summary dialog shown after a successful Organize run."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from app.core.organize import OrganizeResult
from app.core.utils import human_size


def _format_secs(s: float) -> str:
    if s < 60:
        return f"{s:.1f} s"
    m, sec = divmod(int(s), 60)
    return f"{m}m {sec}s"


class StatsDialog(QDialog):
    """Compact end-of-run summary with category breakdown."""

    def __init__(self, result: OrganizeResult, *,
                 category_lookup=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Organize complete")
        self.setMinimumWidth(420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(10)

        moved = QLabel(f"<b>{result.moved}</b> file(s) moved")
        moved.setStyleSheet("font-size: 16px;")
        outer.addWidget(moved)

        summary = QLabel(
            f"Total size: {human_size(result.bytes_total)}    ·    "
            f"Elapsed: {_format_secs(result.elapsed_seconds)}    ·    "
            f"Errors: {result.errors}"
        )
        summary.setStyleSheet("color: #9ba0ab;")
        outer.addWidget(summary)

        # Per-category breakdown
        per_cat = result.per_category or {}
        if per_cat:
            outer.addSpacing(6)
            outer.addWidget(self._breakdown(per_cat, category_lookup))

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.accept)
        outer.addWidget(buttons)

    @staticmethod
    def _breakdown(per_cat: dict[str, int], lookup) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        # Sort by descending count; ties keep insertion order.
        items = sorted(per_cat.items(), key=lambda kv: (-kv[1], kv[0]))
        for cat_id, count in items:
            label = lookup(cat_id) if lookup else cat_id
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(QLabel(label or cat_id))
            row.addStretch(1)
            count_label = QLabel(str(count))
            count_label.setAlignment(Qt.AlignRight)
            count_label.setStyleSheet("color: #9ba0ab; min-width: 30px;")
            row.addWidget(count_label)
            layout.addLayout(row)
        return container
