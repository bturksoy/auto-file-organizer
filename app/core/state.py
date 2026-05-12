"""In-memory app state shared across pages.

Wraps the persisted AppData plus runtime-only bits (current folder, last
plan, last result). Emits a Qt signal whenever something changes so pages
can re-render without polling.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.core.i18n import i18n
from app.core.models import AppData, Profile
from app.core.organize import OrganizeResult, PlannedMove
from app.core.storage import load_app_data, save_app_data


class AppState(QObject):
    profiles_changed = Signal()
    active_profile_changed = Signal()
    folder_changed = Signal(object)        # Path | None
    plan_ready = Signal(list)              # list[PlannedMove]
    organize_finished = Signal(object)     # OrganizeResult

    def __init__(self) -> None:
        super().__init__()
        self.data: AppData = load_app_data()
        i18n.set_language(self.data.language)
        self.current_folder: Path | None = None
        self.last_plan: list[PlannedMove] = []
        self.last_result: OrganizeResult | None = None

    # ------- Profiles ------------------------------------------------------

    def active_profile(self) -> Profile | None:
        return self.data.active_profile()

    def set_active_profile(self, profile_id: str) -> None:
        self.data.active_profile_id = profile_id
        self.save()
        self.active_profile_changed.emit()

    def add_profile(self, profile: Profile) -> None:
        self.data.profiles.append(profile)
        self.save()
        self.profiles_changed.emit()

    def remove_profile(self, profile_id: str) -> None:
        self.data.profiles = [p for p in self.data.profiles if p.id != profile_id]
        if self.data.active_profile_id == profile_id and self.data.profiles:
            self.data.active_profile_id = self.data.profiles[0].id
            self.active_profile_changed.emit()
        self.save()
        self.profiles_changed.emit()

    # ------- Folders -------------------------------------------------------

    def set_folder(self, folder: Path | None) -> None:
        self.current_folder = folder
        if folder:
            self._remember_recent(str(folder))
        self.folder_changed.emit(folder)

    def _remember_recent(self, folder: str) -> None:
        recent = list(self.data.recent_folders)
        if folder in recent:
            recent.remove(folder)
        recent.insert(0, folder)
        self.data.recent_folders = recent[:8]
        self.save()

    # ------- Persistence ---------------------------------------------------

    def save(self) -> None:
        save_app_data(self.data)

    def set_language(self, code: str) -> None:
        self.data.language = code
        i18n.set_language(code)
        self.save()
