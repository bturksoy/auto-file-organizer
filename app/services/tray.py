"""System tray icon backed by QSystemTrayIcon."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayController(QObject):
    show_requested = Signal()
    run_now_requested = Signal()
    toggle_pause_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None, *, icon: QIcon | None = None) -> None:
        super().__init__(parent)
        tray_icon = icon if icon and not icon.isNull() else self._make_icon()
        self._icon = QSystemTrayIcon(tray_icon, parent)
        self._icon.setToolTip("Auto File Organizer")

        menu = QMenu()
        self._show_action = QAction("Show window")
        self._show_action.triggered.connect(self.show_requested.emit)
        menu.addAction(self._show_action)

        self._run_action = QAction("Organize now")
        self._run_action.triggered.connect(self.run_now_requested.emit)
        menu.addAction(self._run_action)

        self._pause_action = QAction("Pause auto-organize")
        self._pause_action.triggered.connect(self.toggle_pause_requested.emit)
        menu.addAction(self._pause_action)

        menu.addSeparator()
        self._quit_action = QAction("Quit")
        self._quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(self._quit_action)

        self._icon.setContextMenu(menu)
        self._icon.activated.connect(self._on_activated)

    def show(self) -> None:
        self._icon.show()

    def hide(self) -> None:
        self._icon.hide()

    def notify(self, message: str, title: str = "Auto File Organizer") -> None:
        if QSystemTrayIcon.supportsMessages():
            self._icon.showMessage(title, message, QSystemTrayIcon.Information)

    def set_pause_label(self, paused: bool) -> None:
        self._pause_action.setText(
            "Resume auto-organize" if paused else "Pause auto-organize"
        )

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_requested.emit()

    @staticmethod
    def _make_icon() -> QIcon:
        pix = QPixmap(64, 64)
        pix.fill(QColor(124, 140, 255))
        painter = QPainter(pix)
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(QColor(255, 255, 255))
        painter.drawRoundedRect(10, 18, 44, 36, 6, 6)
        painter.setBrush(QColor(124, 140, 255))
        painter.drawRect(10, 18, 44, 6)
        painter.end()
        return QIcon(pix)
