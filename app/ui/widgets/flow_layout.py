"""FlowLayout — wraps child widgets onto multiple rows.

Standard Qt example, simplified. Used for extension chips so they wrap
when the card is narrow.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy


class FlowLayout(QLayout):
    def __init__(self, parent=None, *, h_spacing: int = 6,
                 v_spacing: int = 6) -> None:
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items = []

    def addItem(self, item) -> None:  # noqa: N802 (Qt API)
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientations(Qt.Horizontal)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, apply=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        size += QSize(2 * self.contentsMargins().left(),
                      2 * self.contentsMargins().top())
        return size

    def _do_layout(self, rect: QRect, *, apply: bool) -> int:
        x, y = rect.x(), rect.y()
        line_height = 0
        for item in self._items:
            wid = item.widget()
            space_x = self._h_spacing
            space_y = self._v_spacing
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y()
