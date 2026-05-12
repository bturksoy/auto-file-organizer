"""Modal editor for a scanned plan.

Lets the user filter the file list by name, multi-select rows, and
re-assign a batch to a different category before Organize runs.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout,
)

from app.core.classifier import resolve_destination
from app.core.models import Action, Category, Profile
from app.core.organize import PlannedMove


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
        self.setMinimumSize(720, 480)

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

        # Tree: category -> files
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["File", "Reason"])
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setColumnWidth(0, 400)
        layout.addWidget(self._tree, stretch=1)
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
