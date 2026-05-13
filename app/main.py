"""Application entry point.

Bootstraps the QApplication, instantiates global state, wires the tray and
scheduler services, and starts the auto-update check on launch.
"""
from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.state import AppState
from app.core.utils import resources_dir
from app.services.scheduler import Scheduler
from app.services.tray import TrayController
from app.services.watcher import Watcher
from app.services.updates import (
    APP_VERSION, download_and_swap, fetch_latest_release, human_size,
    is_newer, is_running_frozen,
)
from app.ui.main_window import MainWindow
from app.ui.theme import THEMES, build_stylesheet


def app_icon() -> QIcon:
    """Load the app icon (cat in folder) from bundled resources."""
    candidates = [
        resources_dir() / "icon.ico",
        resources_dir() / "icon.png",
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
    box.addButton("Later", QMessageBox.RejectRole)
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


def _run_first_run_wizard(state: AppState, holder: dict) -> None:
    """Show the welcome wizard and persist the user's picks.

    Marking `first_run_seen` happens regardless of how the wizard
    exits — finishing, skipping, or closing the window. The wizard is
    explicitly low-stakes, and we never want to re-show it.
    """
    from app.ui.dialogs.first_run import FirstRunWizard

    parent = holder["window"]
    wiz = FirstRunWizard(state, parent=parent)
    accepted = wiz.exec()
    state.data.first_run_seen = True

    if accepted:
        folder = wiz.selected_folder()
        if folder is not None:
            state.set_folder(folder)
            profile = state.active_profile()
            if profile is not None:
                # The chosen folder also seeds watched_folders so the
                # scheduled / realtime engines pick it up immediately if
                # the user enabled them via the wizard.
                if str(folder) not in profile.settings.watched_folders:
                    profile.settings.watched_folders.append(str(folder))
                if wiz.realtime_requested():
                    profile.settings.background_mode = "realtime"
    state.save()


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

    # ----- Tray + scheduler (live across language switches) -----
    # Mutable holder so closures can resolve the current window even after
    # a language-driven rebuild swaps it out.
    holder: dict = {"window": None}

    tray = TrayController(parent=None, icon=icon if not icon.isNull() else None)
    scheduler = Scheduler(state)
    watcher = Watcher(state)

    def current_window():
        return holder["window"]

    def update_tray_visibility():
        """Reconcile the scheduler/watcher to the active profile's settings.

        background_mode is mutually exclusive: at most one engine runs at
        a time. The tray icon shows whenever either engine is on.
        """
        profile = state.active_profile()
        bg = profile.settings.background_mode if profile else "off"
        wants_scheduler = bg == "scheduled"
        wants_watcher = bg == "realtime" and watcher.is_supported

        if wants_scheduler or wants_watcher:
            tray.show()
        else:
            tray.hide()

        if wants_scheduler:
            if not scheduler.is_running:
                scheduler.start()
        else:
            scheduler.stop()

        # Always restart the watcher when settings/profiles change so a
        # different watched_folders list takes effect immediately.
        if wants_watcher:
            watcher.restart()
        else:
            watcher.stop()

    def show_window():
        w = current_window()
        if w is None:
            return
        w.showNormal()
        w.activateWindow()
        w.raise_()

    def on_pause_toggle():
        paused = scheduler.toggle_pause()
        tray.set_pause_label(paused)

    def quit_app():
        scheduler.stop()
        watcher.stop()
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
    watcher.pass_complete.connect(on_scheduler_pass)

    state.profiles_changed.connect(update_tray_visibility)
    state.active_profile_changed.connect(update_tray_visibility)

    # ----- Auto-update flow -----
    bridge = _UpdateBridge()
    bridge.update_available.connect(
        lambda info: _prompt_update(current_window(), info, state, bridge)
    )

    def _on_update_swapped() -> None:
        """Clean shutdown after the .exe was swapped on disk.

        The previous version called os._exit(0) from a daemon thread,
        which skipped Qt teardown — leaving the .exe handle locked just
        long enough for the relauncher .bat to race the file `move` and
        sometimes fail. Stop services first, then exit the event loop;
        the launcher .bat does the actual relaunch.
        """
        scheduler.stop()
        watcher.stop()
        tray.hide()
        app.quit()
    bridge.update_done.connect(_on_update_swapped)

    bridge.update_failed.connect(
        lambda err: QMessageBox.warning(
            current_window(), "Update failed", err)
    )

    def _build_window() -> MainWindow:
        win = MainWindow(state)
        if not icon.isNull():
            win.setWindowIcon(icon)

        def close_event(event):
            profile = state.active_profile()
            # Minimise to tray instead of quitting when background mode is
            # active. Otherwise close the window normally.
            if profile and profile.settings.background_mode != "off":
                event.ignore()
                win.hide()
            else:
                event.accept()
        win.closeEvent = close_event  # type: ignore[assignment]
        return win

    def _on_language_changed(_code: str) -> None:
        # Hot-swap: build a new MainWindow with refreshed strings, then
        # dispose of the old one. State (profiles, current folder) lives
        # in AppState, so the new window picks everything up.
        old = holder["window"]
        geometry = old.geometry() if old else None
        new = _build_window()
        if geometry is not None:
            new.setGeometry(geometry)
        new.show()
        holder["window"] = new
        if old is not None:
            old.deleteLater()
    state.language_changed.connect(_on_language_changed)

    holder["window"] = _build_window()
    update_tray_visibility()

    # Optional: start hidden if user opted in.
    active = state.active_profile()
    if (active and active.settings.background_mode != "off"
            and active.settings.start_in_tray):
        holder["window"].hide()
    else:
        holder["window"].show()

    # First-run welcome wizard. Runs once per machine (gated on the
    # `first_run_seen` flag) — anyone who really wants it again can flip
    # the flag back to false in appdata.json.
    if not state.data.first_run_seen:
        QTimer.singleShot(150, lambda: _run_first_run_wizard(state, holder))

    QTimer.singleShot(800, lambda: _spawn_update_check(state, bridge))

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
