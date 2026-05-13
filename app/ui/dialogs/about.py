"""About dialog: version, links, license."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QVBoxLayout,
)

from app.core.i18n import i18n


class AboutDialog(QDialog):
    REPO_URL = "https://github.com/bturksoy/auto-file-organizer"
    BMC_URL = "https://buymeacoffee.com/bturksoy"

    def __init__(self, *, icon_path: str | None = None,
                 version: str = "?", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.t("dialog.about.title"))
        self.setMinimumWidth(420)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 16)
        outer.setSpacing(20)

        if icon_path:
            icon_label = QLabel()
            pix = QPixmap(icon_path).scaled(
                96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pix)
            icon_label.setAlignment(Qt.AlignTop)
            outer.addWidget(icon_label)

        body = QVBoxLayout()
        body.setSpacing(6)

        title = QLabel(i18n.t("dialog.about.heading"))
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        body.addWidget(title)

        ver = QLabel(i18n.t("dialog.about.version", version=version))
        ver.setStyleSheet("color: #9ba0ab;")
        body.addWidget(ver)

        desc = QLabel(i18n.t("dialog.about.description"))
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #c5c9d4;")
        body.addWidget(desc)

        body.addSpacing(8)

        github_label = i18n.t("dialog.about.link_github")
        bmc_label = i18n.t("dialog.about.link_bmc")
        license_label = i18n.t("dialog.about.license")
        lic = QLabel(
            f"<a href='{self.REPO_URL}' style='color:#7c8cff;'>{github_label}</a><br>"
            f"<a href='{self.BMC_URL}' style='color:#7c8cff;'>{bmc_label}</a><br>"
            f"{license_label}"
        )
        lic.setOpenExternalLinks(True)
        lic.setTextFormat(Qt.RichText)
        body.addWidget(lic)

        body.addStretch(1)
        outer.addLayout(body, stretch=1)

        btn_row = QDialogButtonBox(QDialogButtonBox.Close)
        btn_row.rejected.connect(self.reject)
        body.addWidget(btn_row)
