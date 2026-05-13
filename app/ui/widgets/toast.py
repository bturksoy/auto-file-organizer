"""Non-modal toast notifications stacked in the top-right of a host widget.

Used in place of QMessageBox.information for low-stakes feedback like
"Organized 12 files" or "Profile saved". Modal QMessageBox is still the
right tool for confirmations, warnings, and errors that need a response.

Usage:

    toast_manager = ToastManager.attach(main_window)
    toast_manager.success("Organized 12 files")
    toast_manager.info("Profile renamed")

Toasts auto-dismiss after a few seconds and can be clicked away early.
"""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QEvent, QObject, QPropertyAnimation, QSize, Qt, QTimer,
    Signal,
)
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from app.ui.theme import active_palette, palette_signal


_TOAST_MARGIN = 16
_TOAST_GAP = 8
_TOAST_WIDTH = 320
_DEFAULT_DURATION_MS = 4000


_KIND_GLYPHS = {
    "info":    "ⓘ",
    "success": "✓",
    "warning": "!",
    "error":   "×",
}


def _kind_color(kind: str) -> str:
    p = active_palette()
    return {
        "info":    p.accent,
        "success": p.success,
        "warning": "#f7c469",
        "error":   p.danger,
    }.get(kind, p.accent)


class Toast(QFrame):
    """A single toast card. Emits `dismissed` when it should be removed."""

    dismissed = Signal(object)  # emits self

    def __init__(self, message: str, *, kind: str = "info",
                 duration_ms: int = _DEFAULT_DURATION_MS,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kind = kind
        self.setObjectName("toast")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.setFixedWidth(_TOAST_WIDTH)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 8, 10)
        layout.setSpacing(10)

        self._glyph = QLabel(_KIND_GLYPHS.get(kind, "ⓘ"))
        self._glyph.setFixedSize(QSize(22, 22))
        self._glyph.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._glyph)

        self._message = QLabel(message)
        self._message.setWordWrap(True)
        layout.addWidget(self._message, stretch=1)

        self._close_btn = QPushButton("×")
        self._close_btn.setObjectName("toastClose")
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setFixedSize(QSize(20, 20))
        self._close_btn.clicked.connect(self.dismiss)
        layout.addWidget(self._close_btn, alignment=Qt.AlignTop)

        # Opacity effect drives both the fade-in on show and fade-out on
        # dismiss. Avoids fighting Qt's compositor over hardware acceleration.
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._fade_anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._lifetime = QTimer(self)
        self._lifetime.setSingleShot(True)
        self._lifetime.timeout.connect(self.dismiss)

        self._restyle()
        palette_signal().connect(self._restyle)

        self._duration_ms = duration_ms

    # ----- Lifecycle ------------------------------------------------------

    def present(self) -> None:
        """Show the toast: fade in, then start the auto-dismiss timer."""
        self.show()
        self._fade_anim.stop()
        self._fade_anim.setDuration(180)
        self._fade_anim.setStartValue(self._opacity.opacity())
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()
        if self._duration_ms > 0:
            self._lifetime.start(self._duration_ms)

    def dismiss(self) -> None:
        """Fade out and emit `dismissed` so the manager can drop us."""
        self._lifetime.stop()
        self._fade_anim.stop()
        self._fade_anim.setDuration(220)
        self._fade_anim.setStartValue(self._opacity.opacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self._on_faded)
        self._fade_anim.start()

    def _on_faded(self) -> None:
        # Disconnect to avoid re-firing if the animation is reused.
        try:
            self._fade_anim.finished.disconnect(self._on_faded)
        except (RuntimeError, TypeError):
            pass
        self.dismissed.emit(self)
        self.hide()
        self.deleteLater()

    # ----- Painting -------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        # Manual rounded-rect paint so the drop shadow / border stays crisp
        # even when the toast sits over an arbitrary background.
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        palette = active_palette()
        # Left accent bar in the kind colour, body in card colour.
        bar_width = 4
        radius = 8
        rect = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(Qt.NoPen)
        p.setBrush(Qt.GlobalColor.transparent)
        p.drawRoundedRect(rect, radius, radius)
        from PySide6.QtGui import QColor
        p.setBrush(QColor(palette.bg_card))
        p.drawRoundedRect(rect, radius, radius)
        # Stripe on the left edge.
        p.setBrush(QColor(_kind_color(self._kind)))
        p.drawRect(rect.x(), rect.y() + 4, bar_width, rect.height() - 8)
        # 1px border to lift it off the bg.
        from PySide6.QtGui import QPen
        p.setBrush(Qt.NoBrush)
        pen = QPen(QColor(palette.border))
        pen.setWidth(1)
        p.setPen(pen)
        p.drawRoundedRect(rect, radius, radius)
        super().paintEvent(event)

    def _restyle(self) -> None:
        p = active_palette()
        self._message.setStyleSheet(f"color: {p.text}; font-size: 13px;")
        self._glyph.setStyleSheet(
            f"color: {_kind_color(self._kind)}; font-size: 18px;"
            " font-weight: 700;")
        self._close_btn.setStyleSheet(
            f"QPushButton#toastClose {{ color: {p.text_dim};"
            " background: transparent; border: none; font-size: 16px; }"
            f"QPushButton#toastClose:hover {{ color: {p.text}; }}"
        )


class ToastManager:
    """Owns the toast stack on a host widget.

    The host widget can be any QWidget; we listen for its resize events
    so the stack stays anchored to the top-right corner.
    """

    def __init__(self, host: QWidget) -> None:
        self._host = host
        self._toasts: list[Toast] = []
        # Catch host resizes to keep toasts pinned to the top-right.
        host.installEventFilter(_HostResizeFilter(self))

    # ----- Public API ----------------------------------------------------

    @classmethod
    def attach(cls, host: QWidget) -> "ToastManager":
        existing = getattr(host, "_toast_manager", None)
        if existing is not None:
            return existing
        mgr = cls(host)
        host._toast_manager = mgr  # type: ignore[attr-defined]
        return mgr

    def info(self, message: str, **kw) -> Toast:
        return self.show(message, kind="info", **kw)

    def success(self, message: str, **kw) -> Toast:
        return self.show(message, kind="success", **kw)

    def warning(self, message: str, **kw) -> Toast:
        return self.show(message, kind="warning", **kw)

    def error(self, message: str, **kw) -> Toast:
        return self.show(message, kind="error", **kw)

    def show(self, message: str, *, kind: str = "info",
             duration_ms: int = _DEFAULT_DURATION_MS) -> Toast:
        toast = Toast(message, kind=kind, duration_ms=duration_ms,
                      parent=self._host)
        toast.dismissed.connect(self._on_dismissed)
        self._toasts.append(toast)
        self._reflow()
        toast.present()
        return toast

    # ----- Internals -----------------------------------------------------

    def _on_dismissed(self, toast: Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._reflow()

    def _reflow(self) -> None:
        host_w = self._host.width()
        y = _TOAST_MARGIN
        for toast in self._toasts:
            # Width is fixed; ensure the toast height is computed before
            # placement so multi-line messages stack cleanly.
            toast.adjustSize()
            x = host_w - toast.width() - _TOAST_MARGIN
            toast.move(x, y)
            toast.raise_()
            y += toast.height() + _TOAST_GAP


class _HostResizeFilter(QObject):
    """Resize watcher so the stack stays anchored to the host's top-right."""

    def __init__(self, manager: ToastManager) -> None:
        super().__init__(manager._host)
        self._manager = manager

    def eventFilter(self, _obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Resize:
            self._manager._reflow()
        return False
