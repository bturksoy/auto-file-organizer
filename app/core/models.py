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
# v2.7 trimmed the new-rule menu to these 11 types. The classifier still
# evaluates the older types (name_does_not_contain, extension_is,
# modified_after, modified_before) for rules saved by v2.6, but the rule
# editor no longer offers them — fewer choices, easier picker.
CONDITION_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("name_contains",     "Name contains"),
    ("name_starts_with",  "Name starts with"),
    ("name_ends_with",    "Name ends with"),
    ("name_regex",        "Name matches regex"),
    ("extension_in",      "Extension is one of"),
    ("path_contains",     "Path contains"),
    ("size_above_mb",     "Size above (MB)"),
    ("size_below_mb",     "Size below (MB)"),
    ("age_above_days",    "Older than (days)"),
    ("age_below_days",    "Newer than (days)"),
    ("content_matches",   "Content matches pattern"),
)
CONDITION_TYPES = tuple(t for t, _ in CONDITION_DEFINITIONS)
CONDITION_LABELS = dict(CONDITION_DEFINITIONS)

# Legacy types kept alive for backwards compatibility but absent from the
# new-rule dropdown. Labels here cover existing rules displayed in cards.
LEGACY_CONDITION_LABELS = {
    "name_does_not_contain": "Name does NOT contain",
    "extension_is":          "Extension is",
    "modified_after":        "Modified after",
    "modified_before":       "Modified before",
}

# --- Action types -----------------------------------------------------------
# Whether to move or copy is set on the Rule itself (`is_copy`), so we only
# need two action verbs. The "skip" action that used to live here is gone —
# the `rules_only` organization mode does the same thing more honestly.
ACTION_TYPES = (
    "move_to_category",       # target = category id
    "move_to_folder",         # target = absolute folder path
)


# Map legacy persisted action types onto the new (type, is_copy) pair.
_LEGACY_ACTION_MIGRATION = {
    "copy_to_category": ("move_to_category", True),
    "copy_to_folder":   ("move_to_folder", True),
    "skip":             ("move_to_category", False),  # neutralised; rule disabled
}


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
    # Optional Python str.format template applied to the destination
    # filename. Tokens: {stem} {ext} {name} {year} {month} {day}.
    # Example: "{stem}_{year}-{month}{ext}".
    rename_template: str = ""

    @staticmethod
    def from_dict(d: dict) -> "Action":
        return Action(
            type=str(d.get("type", "")),
            target=str(d.get("target", "")),
            rename_template=str(d.get("rename_template") or ""),
        )


@dataclass
class ConditionGroup:
    """Tree node for AND/OR rule logic.

    A group has an operator ("and" or "or") and a list of items where
    each item is either a Condition or another ConditionGroup. Leaving
    the operator at "and" with a flat list of Conditions reproduces the
    pre-v2.6 behaviour exactly.
    """
    operator: str = "and"
    items: list = field(default_factory=list)  # list[Condition | ConditionGroup]

    @staticmethod
    def from_dict(d: dict) -> "ConditionGroup":
        op = str(d.get("operator") or "and").lower()
        if op not in ("and", "or"):
            op = "and"
        out: list = []
        for raw in d.get("items", []):
            if isinstance(raw, dict):
                if "operator" in raw:
                    out.append(ConditionGroup.from_dict(raw))
                else:
                    out.append(Condition.from_dict(raw))
        return ConditionGroup(operator=op, items=out)


@dataclass
class Rule:
    id: str
    name: str
    enabled: bool = True
    # `conditions` is the flat AND list kept for backwards compatibility.
    # `condition_root` is the new tree representation; when set, it takes
    # precedence. Old configs load with condition_root=None and continue
    # to evaluate via the flat list.
    conditions: list[Condition] = field(default_factory=list)
    condition_root: ConditionGroup | None = None
    action: Action = field(
        default_factory=lambda: Action(type="move_to_category"))
    # When True, the matched file is duplicated to the destination instead
    # of moved. Replaces the old copy_to_* action variants.
    is_copy: bool = False

    @staticmethod
    def from_dict(d: dict) -> "Rule":
        flat = [Condition.from_dict(c) for c in d.get("conditions", [])]
        root = None
        if isinstance(d.get("condition_root"), dict):
            root = ConditionGroup.from_dict(d["condition_root"])
        action = Action.from_dict(d.get("action", {}))
        is_copy = bool(d.get("is_copy", False))
        enabled = bool(d.get("enabled", True))
        # Migrate legacy action types (copy_to_*, skip) to the new pair.
        if action.type in _LEGACY_ACTION_MIGRATION:
            new_type, new_copy = _LEGACY_ACTION_MIGRATION[action.type]
            if action.type == "skip":
                enabled = False
            action.type = new_type
            is_copy = is_copy or new_copy
        return Rule(
            id=str(d.get("id") or uuid.uuid4().hex),
            name=str(d.get("name", "")),
            enabled=enabled,
            conditions=flat,
            condition_root=root,
            action=action,
            is_copy=is_copy,
        )


@dataclass
class ContentPattern:
    """A user-defined "smart detector" mirroring the CV signal lists.

    Strong / weak keyword lists are matched against extracted PDF/DOCX
    text. A file is considered a match if it has any strong hit or at
    least `weak_threshold` weak hits.
    """
    id: str
    name: str
    strong: list[str] = field(default_factory=list)
    weak: list[str] = field(default_factory=list)
    weak_threshold: int = 2

    @staticmethod
    def from_dict(d: dict) -> "ContentPattern":
        return ContentPattern(
            id=str(d.get("id") or uuid.uuid4().hex),
            name=str(d.get("name", "")),
            strong=list(d.get("strong", []) or []),
            weak=list(d.get("weak", []) or []),
            weak_threshold=max(1, int(d.get("weak_threshold", 2) or 2)),
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
    # List of folders the scheduler / watcher iterate over.
    watched_folders: list[str] = field(default_factory=list)
    # `background_mode` replaces the auto_organize + realtime_watch bool
    # pair from v2.6. Mutually exclusive: at most one engine runs at a
    # time. Accepts "off", "scheduled", "realtime".
    background_mode: str = "off"
    auto_interval_min: int = 30
    start_in_tray: bool = False
    recursive_scan: bool = False
    inspect_pdf_docx: bool = True

    @staticmethod
    def from_dict(d: dict) -> "ProfileSettings":
        mode = str(d.get("organization_mode") or "rules_then_categories")
        if mode not in ORG_MODES:
            mode = "rules_then_categories"
        # Migrate from the v2.1-v2.3 singular `watched_folder` field.
        legacy = str(d.get("watched_folder", "") or "").strip()
        folders = [
            str(p).strip() for p in (d.get("watched_folders") or [])
            if str(p).strip()
        ]
        if legacy and legacy not in folders:
            folders.insert(0, legacy)
        # Migrate v2.6 auto_organize / realtime_watch bool pair to the
        # background_mode enum. Real-time wins if both were enabled.
        bg = str(d.get("background_mode") or "").lower()
        if bg not in ("off", "scheduled", "realtime"):
            if bool(d.get("realtime_watch", False)):
                bg = "realtime"
            elif bool(d.get("auto_organize", False)):
                bg = "scheduled"
            else:
                bg = "off"
        return ProfileSettings(
            organization_mode=mode,
            show_notifications=bool(d.get("show_notifications", True)),
            destination_folder=str(d.get("destination_folder", "")),
            watched_folders=folders,
            background_mode=bg,
            auto_interval_min=max(1, int(d.get("auto_interval_min", 30) or 30)),
            start_in_tray=bool(d.get("start_in_tray", False)),
            recursive_scan=bool(d.get("recursive_scan", False)),
            inspect_pdf_docx=bool(d.get("inspect_pdf_docx", True)),
        )


@dataclass
class Profile:
    id: str
    name: str
    color: str = "#7c8cff"
    rules: list[Rule] = field(default_factory=list)
    categories: list[Category] = field(default_factory=list)
    content_patterns: list[ContentPattern] = field(default_factory=list)
    settings: ProfileSettings = field(default_factory=ProfileSettings)

    @staticmethod
    def from_dict(d: dict) -> "Profile":
        return Profile(
            id=str(d.get("id") or uuid.uuid4().hex),
            name=str(d.get("name", "Profile")),
            color=str(d.get("color") or "#7c8cff"),
            rules=[Rule.from_dict(r) for r in d.get("rules", [])],
            categories=[Category.from_dict(c) for c in d.get("categories", [])],
            content_patterns=[
                ContentPattern.from_dict(p)
                for p in d.get("content_patterns", []) or []
            ],
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
    theme: str = "dark"
    check_updates_on_startup: bool = True
    recent_folders: list[str] = field(default_factory=list)
    dismissed_update_version: str = ""
    # Set to True once the first-run wizard has been shown (whether the
    # user finished or skipped it). Persisted so the wizard doesn't
    # reappear on every launch.
    first_run_seen: bool = False

    @staticmethod
    def from_dict(d: dict) -> "AppData":
        theme = str(d.get("theme") or "dark")
        if theme not in ("dark", "light"):
            theme = "dark"
        return AppData(
            active_profile_id=str(d.get("active_profile_id", "")),
            profiles=[Profile.from_dict(p) for p in d.get("profiles", [])],
            language=str(d.get("language", "en")),
            theme=theme,
            check_updates_on_startup=bool(d.get("check_updates_on_startup", True)),
            recent_folders=list(d.get("recent_folders", [])),
            dismissed_update_version=str(d.get("dismissed_update_version", "")),
            first_run_seen=bool(d.get("first_run_seen", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def active_profile(self) -> Profile | None:
        for p in self.profiles:
            if p.id == self.active_profile_id:
                return p
        return self.profiles[0] if self.profiles else None
