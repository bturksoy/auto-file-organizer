"""Real-time folder watcher backed by watchdog.

When the active profile's `background_mode` is "realtime", an Observer is
attached to every watched folder. New / moved files trigger a debounced
organize pass on that folder (debounced because file downloads usually
fire multiple events as the file grows).

Mutually exclusive with the timed Scheduler — only one engine runs at a
time, decided by the radio button on the Settings page.
"""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.core.organize import apply_plan, scan_folder
from app.core.state import AppState

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _HAVE_WATCHDOG = True
except Exception:  # pragma: no cover — watchdog missing in dev shell
    Observer = None  # type: ignore[assignment]
    FileSystemEventHandler = object  # type: ignore[misc, assignment]
    _HAVE_WATCHDOG = False


_DEBOUNCE_SECONDS = 2.5


class _DebouncedHandler(FileSystemEventHandler):  # type: ignore[misc]
    """Coalesces a burst of file events into a single scheduled callback."""

    def __init__(self, fire) -> None:
        super().__init__()
        self._fire = fire
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def on_created(self, event):
        if not event.is_directory:
            self._schedule()

    def on_moved(self, event):
        if not event.is_directory:
            self._schedule()

    def on_modified(self, event):
        # `modified` fires constantly while a file is being written; only
        # the debounce trailing edge actually triggers organize.
        if not event.is_directory:
            self._schedule()

    def _schedule(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(_DEBOUNCE_SECONDS, self._fire)
            self._timer.daemon = True
            self._timer.start()


class Watcher(QObject):
    """Toggle-able real-time watcher tied to AppState."""
    pass_complete = Signal(str, int)

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self._state = state
        self._observer = None

    @property
    def is_supported(self) -> bool:
        return _HAVE_WATCHDOG

    @property
    def is_running(self) -> bool:
        return self._observer is not None

    def start(self) -> None:
        if not _HAVE_WATCHDOG or self._observer is not None:
            return
        profile = self._state.active_profile()
        if not profile:
            return
        folders = [
            f.strip() for f in (profile.settings.watched_folders or [])
            if f and f.strip()
        ]
        if not folders:
            return
        recursive = bool(profile.settings.recursive_scan)
        self._observer = Observer()
        for folder in folders:
            path = Path(folder)
            if not path.is_dir():
                continue
            handler = _DebouncedHandler(lambda p=path: self._fire(p))
            self._observer.schedule(handler, str(path), recursive=recursive)
        self._observer.start()

    def stop(self) -> None:
        if self._observer is None:
            return
        try:
            self._observer.stop()
            self._observer.join(timeout=3)
        except Exception:
            pass
        self._observer = None

    def restart(self) -> None:
        self.stop()
        self.start()

    def _fire(self, folder: Path) -> None:
        profile = self._state.active_profile()
        if not profile:
            return
        try:
            plan = scan_folder(folder, profile)
            if not plan:
                return
            result = apply_plan(folder, plan)
            if result.moved > 0:
                self.pass_complete.emit(str(folder), result.moved)
        except Exception:
            pass
