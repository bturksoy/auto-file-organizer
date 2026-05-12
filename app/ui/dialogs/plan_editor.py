"""Modal editor for a scanned plan.

Lets the user filter the file list by name, multi-select rows, and
re-assign a batch to a different category before Organize runs.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSplitter,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.core.classifier import resolve_destination
from app.core.content import read_docx_text, read_pdf_text
from app.core.models import Action, Category, Profile
from app.core.organize import PlannedMove


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".ico"}
_TEXT_EXTS = {".txt", ".md", ".log", ".csv", ".json", ".xml", ".yml",
              ".yaml", ".py", ".js", ".html", ".css", ".ini", ".cfg"}


class PlanEditorDialog(QDialog):
    """Browse the plan, filter by name, bulk-reassign multi-selection."""

    plan_changed = Signal()

    def __init__(self, plan: list[PlannedMove], profile: Profile,
                 parent=None) -> None:
        super().__init__(parent)
        self._plan = plan
        self._profile = profile
        self._categories: list[Category] = [
            c for c in profile.categories if c.enabled or c.locked
        ]

        self.setWindowTitle("Edit organize plan")
        self.setMinimumSize(960, 560)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel(
            "Multi-select files (Ctrl+click / Shift+click), choose a "
            "category from the dropdown, then hit Reassign."
        ))

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Type to filter by name...")
        self._filter_edit.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._filter_edit, stretch=1)
        layout.addLayout(filter_row)

        # Tree on the left, preview pane on the right.
        split = QSplitter(Qt.Horizontal)
        layout.addWidget(split, stretch=1)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["File", "Reason"])
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setColumnWidth(0, 400)
        self._tree.itemSelectionChanged.connect(self._update_preview)
        split.addWidget(self._tree)

        self._preview = _PreviewPane()
        split.addWidget(self._preview)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)

        self._refresh_tree()

        # Reassign row
        action_row = QHBoxLayout()
        action_row.addWidget(QLabel("Move selected to:"))
        self._cat_combo = QComboBox()
        for cat in self._categories:
            self._cat_combo.addItem(cat.name, userData=cat.id)
        action_row.addWidget(self._cat_combo, stretch=1)
        reassign = QPushButton("Reassign")
        reassign.setObjectName("primary")
        reassign.setCursor(Qt.PointingHandCursor)
        reassign.clicked.connect(self._reassign_selected)
        action_row.addWidget(reassign)

        skip = QPushButton("Remove from plan")
        skip.setObjectName("secondary")
        skip.setCursor(Qt.PointingHandCursor)
        skip.setToolTip("Don't move the selected files when Organize runs")
        skip.clicked.connect(self._remove_selected)
        action_row.addWidget(skip)

        layout.addLayout(action_row)

        # Bottom buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)

    # ----- tree ------------------------------------------------------------

    def _refresh_tree(self) -> None:
        self._tree.clear()
        grouped: dict[str, list[PlannedMove]] = {}
        for move in self._plan:
            grouped.setdefault(move.category_id, []).append(move)
        cat_names = {c.id: c.name for c in self._profile.categories}

        for cat_id, moves in sorted(
                grouped.items(), key=lambda kv: cat_names.get(kv[0], kv[0])):
            label = cat_names.get(cat_id, cat_id)
            parent = QTreeWidgetItem(self._tree,
                                     [f"{label}  ({len(moves)})", ""])
            parent.setFlags(parent.flags() & ~Qt.ItemIsSelectable)
            parent.setExpanded(True)
            for move in sorted(moves, key=lambda m: m.src.name.lower()):
                child = QTreeWidgetItem(parent, [move.src.name, move.reason])
                child.setData(0, Qt.UserRole, id(move))
        self._tree.resizeColumnToContents(0)

    def _apply_filter(self, text: str) -> None:
        needle = text.lower()
        for i in range(self._tree.topLevelItemCount()):
            parent = self._tree.topLevelItem(i)
            visible_children = 0
            for j in range(parent.childCount()):
                child = parent.child(j)
                show = needle in child.text(0).lower()
                child.setHidden(not show)
                if show:
                    visible_children += 1
            parent.setHidden(visible_children == 0)

    # ----- mutations -------------------------------------------------------

    def _selected_moves(self) -> list[PlannedMove]:
        ids = {item.data(0, Qt.UserRole) for item in self._tree.selectedItems()
               if item.data(0, Qt.UserRole) is not None}
        return [m for m in self._plan if id(m) in ids]

    def _update_preview(self) -> None:
        moves = self._selected_moves()
        if len(moves) == 1:
            self._preview.show_file(moves[0].src)
        elif len(moves) > 1:
            self._preview.show_multi(len(moves))
        else:
            self._preview.show_empty()

    def _reassign_selected(self) -> None:
        targets = self._selected_moves()
        if not targets:
            return
        new_cat_id = self._cat_combo.currentData()
        if not new_cat_id:
            return
        new_action = Action(type="move_to_category", target=new_cat_id)
        for move in targets:
            new_dst = resolve_destination(self._profile, move.src, new_action)
            if new_dst is None:
                continue
            move.category_id = new_cat_id
            move.dst = new_dst
            move.reason = "manual reassign"
            move.is_copy = False
        self.plan_changed.emit()
        self._refresh_tree()
        self._apply_filter(self._filter_edit.text())

    def _remove_selected(self) -> None:
        targets = self._selected_moves()
        if not targets:
            return
        target_ids = {id(m) for m in targets}
        self._plan[:] = [m for m in self._plan if id(m) not in target_ids]
        self.plan_changed.emit()
        self._refresh_tree()
        self._apply_filter(self._filter_edit.text())


def _format_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} GB"


class _PreviewPane(QFrame):
    """Right-hand pane showing a thumbnail or text snippet for one file."""

    _MAX_TEXT_BYTES = 16 * 1024  # don't slurp huge files
    _MAX_TEXT_LINES = 200

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("previewPane")
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._name_label = QLabel()
        self._name_label.setStyleSheet("font-weight: 600;")
        self._name_label.setWordWrap(True)
        layout.addWidget(self._name_label)

        self._meta_label = QLabel()
        self._meta_label.setStyleSheet("color: #9ba0ab; font-size: 11px;")
        self._meta_label.setWordWrap(True)
        layout.addWidget(self._meta_label)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setMinimumSize(QSize(220, 220))
        self._image_label.setStyleSheet(
            "background-color: rgba(0,0,0,0.18); border-radius: 6px;")
        layout.addWidget(self._image_label, stretch=1)

        self._text_view = QPlainTextEdit()
        self._text_view.setReadOnly(True)
        self._text_view.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        layout.addWidget(self._text_view, stretch=2)

        self.show_empty()

    # ----- view modes ----------------------------------------------------

    def show_empty(self) -> None:
        self._name_label.setText("No file selected")
        self._meta_label.clear()
        self._image_label.clear()
        self._image_label.setText("Select a file in the list to preview it.")
        self._text_view.clear()
        self._text_view.hide()
        self._image_label.show()

    def show_multi(self, count: int) -> None:
        self._name_label.setText(f"{count} files selected")
        self._meta_label.setText(
            "Preview only renders for a single selection.")
        self._image_label.clear()
        self._image_label.setText("…")
        self._text_view.clear()
        self._text_view.hide()
        self._image_label.show()

    def show_file(self, path: Path) -> None:
        self._name_label.setText(path.name)
        try:
            st = path.stat()
            self._meta_label.setText(
                f"{_format_size(st.st_size)} • "
                f"modified {datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M}"
                f" • {path.parent}"
            )
        except OSError:
            self._meta_label.setText(str(path.parent))

        ext = path.suffix.lower()
        if ext in _IMAGE_EXTS:
            self._render_image(path)
            return
        if ext == ".pdf":
            self._render_text(self._safe_pdf_text(path),
                              fallback="(PDF text could not be extracted)")
            return
        if ext == ".docx":
            self._render_text(self._safe_docx_text(path),
                              fallback="(DOCX text could not be extracted)")
            return
        if ext in _TEXT_EXTS:
            self._render_text(self._safe_plain_text(path),
                              fallback="(file is empty)")
            return
        # Unknown binary: show file info only.
        self._image_label.clear()
        self._image_label.setText(
            f"No preview available for {ext or 'this file type'}.")
        self._text_view.clear()
        self._text_view.hide()
        self._image_label.show()

    # ----- renderers -----------------------------------------------------

    def _render_image(self, path: Path) -> None:
        pix = QPixmap(str(path))
        if pix.isNull():
            self._image_label.clear()
            self._image_label.setText("(image could not be loaded)")
        else:
            target = self._image_label.size()
            scaled = pix.scaled(
                target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._image_label.setPixmap(scaled)
        self._text_view.hide()
        self._image_label.show()

    def _render_text(self, text: str, fallback: str) -> None:
        if not text.strip():
            text = fallback
        else:
            lines = text.splitlines()
            if len(lines) > self._MAX_TEXT_LINES:
                lines = lines[: self._MAX_TEXT_LINES] + [
                    "",
                    f"… ({len(lines) - self._MAX_TEXT_LINES} more lines)"
                ]
                text = "\n".join(lines)
        self._text_view.setPlainText(text)
        self._image_label.hide()
        self._text_view.show()

    @staticmethod
    def _safe_pdf_text(path: Path) -> str:
        try:
            return read_pdf_text(path, max_pages=2)
        except Exception:
            return ""

    @staticmethod
    def _safe_docx_text(path: Path) -> str:
        try:
            return read_docx_text(path)
        except Exception:
            return ""

    @classmethod
    def _safe_plain_text(cls, path: Path) -> str:
        try:
            with path.open("rb") as f:
                raw = f.read(cls._MAX_TEXT_BYTES)
            for enc in ("utf-8", "utf-16", "latin-1"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return ""
        except OSError:
            return ""
