"""Plain-data models for profiles, categories, rules and settings.

Everything serializes to JSON via dataclasses.asdict and is loaded back with
the from_dict helpers below. Keeping these models simple lets us round-trip
through user-editable JSON files without ORM machinery.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from typing import Any


# --- Condition types accepted by the rules engine ---------------------------
CONDITION_TYPES = (
    "name_contains",
    "name_starts_with",
    "name_ends_with",
    "name_regex",
    "extension_is",
    "size_above_mb",
    "size_below_mb",
)

# --- Action types -----------------------------------------------------------
ACTION_TYPES = (
    "move_to_category",  # target = category id
    "move_to_folder",    # target = absolute folder path
    "skip",              # leave file untouched
)


@dataclass
class Condition:
    type: str
    value: str

    @staticmethod
    def from_dict(d: dict) -> "Condition":
        return Condition(type=str(d.get("type", "")),
                         value=str(d.get("value", "")))


@dataclass
class Action:
    type: str
    target: str = ""

    @staticmethod
    def from_dict(d: dict) -> "Action":
        return Action(type=str(d.get("type", "")),
                      target=str(d.get("target", "")))


@dataclass
class Rule:
    id: str
    name: str
    enabled: bool = True
    conditions: list[Condition] = field(default_factory=list)
    action: Action = field(default_factory=lambda: Action(type="skip"))

    @staticmethod
    def from_dict(d: dict) -> "Rule":
        return Rule(
            id=str(d.get("id") or uuid.uuid4().hex),
            name=str(d.get("name", "")),
            enabled=bool(d.get("enabled", True)),
            conditions=[Condition.from_dict(c) for c in d.get("conditions", [])],
            action=Action.from_dict(d.get("action", {})),
        )


@dataclass
class Category:
    id: str
    name: str
    color: str = "#7c8cff"
    extensions: list[str] = field(default_factory=list)
    target_folder: str = ""
    enabled: bool = True
    locked: bool = False

    @staticmethod
    def from_dict(d: dict) -> "Category":
        return Category(
            id=str(d.get("id") or uuid.uuid4().hex),
            name=str(d.get("name", "")),
            color=str(d.get("color", "#7c8cff")),
            extensions=list(d.get("extensions", [])),
            target_folder=str(d.get("target_folder")
                              or d.get("name", "")),
            enabled=bool(d.get("enabled", True)),
            locked=bool(d.get("locked", False)),
        )


# Settings carried inside each profile (separate from app-wide settings).
ORG_MODES = ("rules_then_categories", "categories_only", "rules_only")


@dataclass
class ProfileSettings:
    organization_mode: str = "rules_then_categories"
    show_notifications: bool = True
    destination_folder: str = ""
    watched_folder: str = ""
    auto_organize: bool = False
    auto_interval_min: int = 30
    start_in_tray: bool = False

    @staticmethod
    def from_dict(d: dict) -> "ProfileSettings":
        mode = str(d.get("organization_mode") or "rules_then_categories")
        if mode not in ORG_MODES:
            mode = "rules_then_categories"
        return ProfileSettings(
            organization_mode=mode,
            show_notifications=bool(d.get("show_notifications", True)),
            destination_folder=str(d.get("destination_folder", "")),
            watched_folder=str(d.get("watched_folder", "")),
            auto_organize=bool(d.get("auto_organize", False)),
            auto_interval_min=max(1, int(d.get("auto_interval_min", 30) or 30)),
            start_in_tray=bool(d.get("start_in_tray", False)),
        )


@dataclass
class Profile:
    id: str
    name: str
    rules: list[Rule] = field(default_factory=list)
    categories: list[Category] = field(default_factory=list)
    settings: ProfileSettings = field(default_factory=ProfileSettings)

    @staticmethod
    def from_dict(d: dict) -> "Profile":
        return Profile(
            id=str(d.get("id") or uuid.uuid4().hex),
            name=str(d.get("name", "Profile")),
            rules=[Rule.from_dict(r) for r in d.get("rules", [])],
            categories=[Category.from_dict(c) for c in d.get("categories", [])],
            settings=ProfileSettings.from_dict(d.get("settings", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AppData:
    """Top-level container persisted to the user's settings file."""
    active_profile_id: str = ""
    profiles: list[Profile] = field(default_factory=list)
    language: str = "en"
    check_updates_on_startup: bool = True
    recent_folders: list[str] = field(default_factory=list)
    dismissed_update_version: str = ""

    @staticmethod
    def from_dict(d: dict) -> "AppData":
        return AppData(
            active_profile_id=str(d.get("active_profile_id", "")),
            profiles=[Profile.from_dict(p) for p in d.get("profiles", [])],
            language=str(d.get("language", "en")),
            check_updates_on_startup=bool(d.get("check_updates_on_startup", True)),
            recent_folders=list(d.get("recent_folders", [])),
            dismissed_update_version=str(d.get("dismissed_update_version", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def active_profile(self) -> Profile | None:
        for p in self.profiles:
            if p.id == self.active_profile_id:
                return p
        return self.profiles[0] if self.profiles else None
