"""Application entry point.

Bootstraps the QApplication, instantiates global state, wires the tray and
scheduler services, and starts the auto-update check on launch.
"""
from __future__ import annotations

import os
import sys
import threading

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.state import AppState
from app.services.scheduler import Scheduler
from app.services.tray import TrayController
from app.services.updates import (
    APP_VERSION, download_and_swap, fetch_latest_release, human_size,
    is_newer, is_running_frozen,
)
from app.ui.main_window import MainWindow
from app.ui.theme import THEMES, build_stylesheet


def _resources_dir() -> Path:
    """Same lookup the rest of the app uses for bundled files."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "resources"
    return Path(__file__).resolve().parent.parent / "resources"


def app_icon() -> QIcon:
    """Load the app icon (cat in folder) from bundled resources."""
    candidates = [
        _resources_dir() / "icon.ico",
        _resources_dir() / "icon.png",
    ]
    for path in candidates:
        if path.is_file():
            return QIcon(str(path))
    return QIcon()


class _UpdateBridge(QObject):
    """Marshal update-check results from a worker thread back to the GUI."""
    update_available = Signal(dict)
    update_done = Signal()
    update_failed = Signal(str)


def _spawn_update_check(state: AppState, bridge: _UpdateBridge) -> None:
    if not state.data.check_updates_on_startup:
        return
    if not is_running_frozen():
        return

    def worker():
        info = fetch_latest_release()
        if not info:
            return
        if not is_newer(info["version"], APP_VERSION):
            return
        if state.data.dismissed_update_version and \
                not is_newer(info["version"], state.data.dismissed_update_version):
            return
        bridge.update_available.emit(info)

    threading.Thread(target=worker, daemon=True).start()


def _prompt_update(parent, info: dict, state: AppState,
                   bridge: _UpdateBridge) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Information)
    box.setWindowTitle("Update available")
    box.setText(
        f"Version v{info['version']} is available "
        f"(you have v{APP_VERSION}).\n"
        f"Download size: {human_size(info['size'])}.\n\nInstall now?"
    )
    install_btn = box.addButton("Install", QMessageBox.AcceptRole)
    later_btn = box.addButton("Later", QMessageBox.RejectRole)
    dismiss_btn = box.addButton("Skip this version", QMessageBox.DestructiveRole)
    box.exec()

    clicked = box.clickedButton()
    if clicked is install_btn:
        _start_install(info, bridge)
    elif clicked is dismiss_btn:
        state.data.dismissed_update_version = info["version"]
        state.save()


def _start_install(info: dict, bridge: _UpdateBridge) -> None:
    def worker():
        try:
            download_and_swap(info["url"])
        except Exception as exc:  # noqa: BLE001
            bridge.update_failed.emit(str(exc))
            return
        bridge.update_done.emit()
    threading.Thread(target=worker, daemon=True).start()


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Auto File Organizer")
    app.setOrganizationName("FileOrganizer")
    app.setFont(QFont("Segoe UI", 9))

    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    state = AppState()
    # Apply theme from saved settings, then re-apply on every change.
    def _apply_theme(name: str) -> None:
        from app.ui.theme import set_active_palette
        palette = THEMES.get(name) or THEMES["dark"]
        set_active_palette(palette)
        app.setStyleSheet(build_stylesheet(palette))
        for w in app.allWidgets():
            w.update()
    _apply_theme(state.data.theme)
    state.theme_changed.connect(_apply_theme)

    window = MainWindow(state)
    if not icon.isNull():
        window.setWindowIcon(icon)

    # Language hot-swap requires rebuilding many widgets; we accept a
    # restart in v2.2 and surface a hint when the user changes it.
    def _on_language_changed(_code: str) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            window,
            "Language",
            "Language has been saved. Restart the app to apply the new "
            "interface language.",
        )
    state.language_changed.connect(_on_language_changed)

    # ----- Tray + scheduler -----
    tray = TrayController(window, icon=icon if not icon.isNull() else None)
    scheduler = Scheduler(state)

    def update_tray_visibility():
        profile = state.active_profile()
        if profile and profile.settings.auto_organize:
            tray.show()
            if not scheduler.is_running:
                scheduler.start()
        else:
            tray.hide()
            scheduler.stop()

    def show_window():
        window.showNormal()
        window.activateWindow()
        window.raise_()

    def on_pause_toggle():
        paused = scheduler.toggle_pause()
        tray.set_pause_label(paused)

    def quit_app():
        scheduler.stop()
        tray.hide()
        app.quit()

    tray.show_requested.connect(show_window)
    tray.run_now_requested.connect(scheduler.run_now)
    tray.toggle_pause_requested.connect(on_pause_toggle)
    tray.quit_requested.connect(quit_app)

    def on_scheduler_pass(folder: str, moved: int):
        profile = state.active_profile()
        if profile and profile.settings.show_notifications:
            tray.notify(f"Organized {moved} file(s) in {folder}")

    scheduler.pass_complete.connect(on_scheduler_pass)

    state.profiles_changed.connect(update_tray_visibility)
    state.active_profile_changed.connect(update_tray_visibility)
    update_tray_visibility()

    # ----- Override close behavior when auto-organize is on -----
    def close_event(event):
        profile = state.active_profile()
        if profile and profile.settings.auto_organize:
            event.ignore()
            window.hide()
        else:
            event.accept()
    window.closeEvent = close_event  # type: ignore[assignment]

    # Optional: start hidden if user opted in.
    active = state.active_profile()
    if active and active.settings.auto_organize and active.settings.start_in_tray:
        window.hide()
    else:
        window.show()

    # ----- Auto-update flow -----
    bridge = _UpdateBridge()
    bridge.update_available.connect(
        lambda info: _prompt_update(window, info, state, bridge)
    )
    bridge.update_done.connect(lambda: os._exit(0))
    bridge.update_failed.connect(
        lambda err: QMessageBox.warning(window, "Update failed", err)
    )
    QTimer.singleShot(800, lambda: _spawn_update_check(state, bridge))

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
