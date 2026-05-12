"""Card widget for a single Rule, with drag-to-reorder support."""
from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDrag, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from app.core.models import Action, Condition, Rule
from app.ui.widgets.card import Card
from app.ui.widgets.toggle import Toggle


_CONDITION_LABELS = {
    "name_contains": "Name contains",
    "name_does_not_contain": "Name does NOT contain",
    "name_starts_with": "Name starts with",
    "name_ends_with": "Name ends with",
    "name_regex": "Name matches regex",
    "extension_is": "Extension is",
    "extension_in": "Extension in",
    "path_contains": "Path contains",
    "size_above_mb": "Size above (MB)",
    "size_below_mb": "Size below (MB)",
    "age_above_days": "Older than (days)",
    "age_below_days": "Newer than (days)",
}


def describe_condition(c: Condition) -> str:
    label = _CONDITION_LABELS.get(c.type, c.type)
    return f"{label} \"{c.value}\""


def describe_action(action: Action, *, category_lookup=None) -> str:
    verb_map = {
        "move_to_category": "Move",
        "copy_to_category": "Copy",
        "move_to_folder": "Move",
        "copy_to_folder": "Copy",
    }
    verb = verb_map.get(action.type)
    if action.type in ("move_to_category", "copy_to_category"):
        name = category_lookup(action.target) if category_lookup else None
        return f"→ {verb} to {name or action.target}"
    if action.type in ("move_to_folder", "copy_to_folder"):
        return f"→ {verb} to {action.target or '...'}"
    return "→ Skip"


MIME_RULE_ID = "application/x-fileorganizer-rule-id"


class RuleCard(Card):
    edit_requested = Signal(str)
    delete_requested = Signal(str)
    toggled = Signal(str, bool)
    drop_received = Signal(str, str)  # (dropped_id, target_id)

    def __init__(self, rule: Rule, *, category_lookup=None,
                 match_count: int | None = None, parent=None) -> None:
        super().__init__(parent)
        self._rule = rule
        self._category_lookup = category_lookup

        self.setAcceptDrops(True)

        header = QHBoxLayout()
        header.setSpacing(10)

        handle = QLabel("≡")
        handle.setObjectName("dragHandle")
        handle.setCursor(Qt.OpenHandCursor)
        handle.setToolTip("Drag to reorder priority")
        handle.mousePressEvent = self._start_drag  # type: ignore[assignment]
        header.addWidget(handle)

        self.toggle = Toggle(checked=rule.enabled)
        self.toggle.toggled.connect(
            lambda v: self.toggled.emit(self._rule.id, v))
        header.addWidget(self.toggle)

        name_label = QLabel(rule.name or "(unnamed)")
        name_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        header.addWidget(name_label)

        header.addStretch(1)

        badge_text = "No matches" if not match_count else f"{match_count} matched"
        chip = QLabel(badge_text)
        chip.setObjectName("chipNeutral" if not match_count else "chipAccent")
        header.addWidget(chip)

        edit_btn = QPushButton("✎")
        edit_btn.setObjectName("iconBtn")
        edit_btn.setFixedSize(30, 30)
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.setToolTip("Edit rule")
        edit_btn.clicked.connect(
            lambda: self.edit_requested.emit(self._rule.id))
        header.addWidget(edit_btn)

        del_btn = QPushButton("✕")
        del_btn.setObjectName("iconBtn")
        del_btn.setFixedSize(30, 30)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setToolTip("Delete rule")
        del_btn.clicked.connect(
            lambda: self.delete_requested.emit(self._rule.id))
        header.addWidget(del_btn)

        self.layout().addLayout(header)

        # Conditions summary
        for cond in rule.conditions:
            cond_label = QLabel(describe_condition(cond))
            cond_label.setStyleSheet("color: #c5c9d4;")
            self.layout().addWidget(cond_label)

        action_label = QLabel(
            describe_action(rule.action, category_lookup=category_lookup))
        action_label.setStyleSheet(
            "color: #7c8cff; font-size: 13px; font-weight: 500;"
        )
        self.layout().addWidget(action_label)

    # ----- drag-and-drop -----

    def _start_drag(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MIME_RULE_ID, self._rule.id.encode())
        drag.setMimeData(mime)
        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.transparent)
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasFormat(MIME_RULE_ID):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasFormat(MIME_RULE_ID):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        data = event.mimeData().data(MIME_RULE_ID)
        if not data:
            return
        dropped_id = bytes(data).decode()
        if dropped_id == self._rule.id:
            return
        self.drop_received.emit(dropped_id, self._rule.id)
        event.acceptProposedAction()
