"""A switch-style toggle implemented as a custom QAbstractButton.

QCheckBox can be styled with QSS but the indicator stays a square. This
version paints a pill background with a sliding knob, which matches the
FolderFresh look more closely.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QSizePolicy


class Toggle(QAbstractButton):
    TRACK_OFF = QColor("#3a3d46")
    TRACK_ON = QColor("#5a8dff")
    KNOB = QColor("#f4f6fb")

    def __init__(self, parent=None, *, checked: bool = False) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(40, 22)
        self._knob = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob_pos", self)
        self._anim.setDuration(140)
        self.toggled.connect(self._animate)

    # Qt property used by the animator.
    def _get_knob(self) -> float:
        return self._knob

    def _set_knob(self, v: float) -> None:
        self._knob = v
        self.update()

    knob_pos = Property(float, _get_knob, _set_knob)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._knob)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        track = self.TRACK_OFF if not self.isChecked() else self.TRACK_ON
        if self._knob and not self.isChecked():
            # Mid-animation while turning off.
            track = self._blend(self.TRACK_OFF, self.TRACK_ON, self._knob)
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        knob_d = rect.height() - 6
        knob_x = 3 + self._knob * (rect.width() - knob_d - 6)
        p.setBrush(self.KNOB)
        p.drawEllipse(QRectF(knob_x, 3, knob_d, knob_d))

    @staticmethod
    def _blend(a: QColor, b: QColor, t: float) -> QColor:
        return QColor(
            int(a.red() * (1 - t) + b.red() * t),
            int(a.green() * (1 - t) + b.green() * t),
            int(a.blue() * (1 - t) + b.blue() * t),
        )

    def hitButton(self, _pos) -> bool:
        return True
