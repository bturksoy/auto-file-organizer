"""Background scheduler: periodically organize the active profile's watched folder."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.core.organize import apply_plan, scan_folder
from app.core.state import AppState


class Scheduler(QObject):
    """Runs a worker thread that re-checks every N minutes.

    Emits `pass_complete(folder_path, moved_count)` whenever it actually
    moves files; ignored when nothing matched.
    """
    pass_complete = Signal(str, int)

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self._state = state
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop.clear()
        self._pause.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def toggle_pause(self) -> bool:
        """Flip the pause flag. Returns the new paused state."""
        if self._pause.is_set():
            self._pause.clear()
            return False
        self._pause.set()
        return True

    def run_now(self) -> None:
        threading.Thread(target=self._run_one_pass, daemon=True).start()

    def _loop(self) -> None:
        # Short initial delay so the UI doesn't fight startup work.
        for _ in range(5):
            if self._stop.is_set():
                return
            time.sleep(1)
        while not self._stop.is_set():
            profile = self._state.active_profile()
            interval_s = 30 * 60
            if profile:
                interval_s = max(60, profile.settings.auto_interval_min * 60)
                if profile.settings.auto_organize and not self._pause.is_set():
                    self._run_one_pass()
            slept = 0
            while slept < interval_s and not self._stop.is_set():
                time.sleep(1)
                slept += 1

    def _run_one_pass(self) -> None:
        """Run organize against every watched folder of the active profile."""
        profile = self._state.active_profile()
        if not profile or not profile.settings.auto_organize:
            return
        targets = [
            f.strip() for f in (profile.settings.watched_folders or [])
            if f and f.strip()
        ]
        # Legacy single-folder fallback for very old configs.
        if not targets and profile.settings.watched_folder:
            targets = [profile.settings.watched_folder.strip()]
        if not targets:
            return

        for target in targets:
            folder = Path(target)
            if not folder.is_dir():
                continue
            try:
                plan = scan_folder(folder, profile)
                if not plan:
                    continue
                result = apply_plan(folder, plan)
                if result.moved > 0:
                    self.pass_complete.emit(str(folder), result.moved)
            except Exception:
                # Silent failure — UI surfaces this via tray notifications
                # only when the user has notifications on.
                continue
