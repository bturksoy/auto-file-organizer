"""Persistent storage for AppData (profiles + global prefs).

Lives at %APPDATA%/FileOrganizer/appdata.json. On first run we seed a
default profile from the bundled resources so the app is usable out of
the box.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from app.core.models import (
    AppData, Category, Profile, ProfileSettings,
)
from app.core.utils import resources_dir


def _config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    d = Path(base) / "FileOrganizer"
    d.mkdir(parents=True, exist_ok=True)
    return d


def appdata_path() -> Path:
    return _config_dir() / "appdata.json"


_DEFAULT_COLORS = {
    "cv": "#a78bfa",
    "invoices": "#fbbf24",
    "payroll": "#fb923c",
    "bank": "#34d399",
    "tax": "#f87171",
    "telecom": "#22d3ee",
    "insurance": "#60a5fa",
    "contracts": "#f472b6",
    "housing": "#facc15",
    "tickets": "#4ade80",
    "visa": "#818cf8",
    "official": "#fb7185",
    "exams": "#fdba74",
    "manuals": "#a3e635",
    "returns": "#fda4af",
    "logs": "#94a3b8",
    "vehicles": "#38bdf8",
    "screenshots": "#c084fc",
    "installers": "#f59e0b",
    "documents": "#3b82f6",
    "spreadsheets": "#10b981",
    "presentations": "#f97316",
    "images": "#a855f7",
    "videos": "#ec4899",
    "music": "#ef4444",
    "archives": "#eab308",
    "code": "#06b6d4",
    "fonts": "#8b5cf6",
    "disk_images": "#64748b",
    "torrents": "#0ea5e9",
    "other": "#6b7280",
}


def _build_default_profile() -> Profile:
    """Compose the out-of-the-box profile from the bundled resource JSON."""
    res = resources_dir()
    try:
        en = json.loads((res / "i18n" / "en.json").read_text(encoding="utf-8"))
        ext_data = json.loads(
            (res / "data" / "extensions.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        en, ext_data = {}, {}

    cat_names: dict = en.get("categories", {}) or {}
    categories: list[Category] = []
    # Extension-based categories first (locked = built-in feel).
    for key, exts in ext_data.items():
        if key.startswith("_"):
            continue
        categories.append(Category(
            id=key,
            name=cat_names.get(key, key.title()),
            color=_DEFAULT_COLORS.get(key, "#7c8cff"),
            extensions=list(exts),
            target_folder=cat_names.get(key, key.title()),
            enabled=True,
            locked=True,
        ))
    # A CV bucket without extension extensions — populated by rules/content.
    if "cv" not in {c.id for c in categories}:
        categories.insert(0, Category(
            id="cv", name=cat_names.get("cv", "CV"),
            color=_DEFAULT_COLORS["cv"],
            extensions=[],
            target_folder=cat_names.get("cv", "CV"),
            enabled=True, locked=True,
        ))
    # Other bucket for anything that doesn't match.
    if "other" not in {c.id for c in categories}:
        categories.append(Category(
            id="other", name=cat_names.get("other", "Other"),
            color=_DEFAULT_COLORS["other"],
            extensions=[],
            target_folder=cat_names.get("other", "Other"),
            enabled=True, locked=True,
        ))

    return Profile(
        id=uuid.uuid4().hex,
        name="Default",
        rules=[],
        categories=categories,
        settings=ProfileSettings(),
    )


def load_app_data() -> AppData:
    path = appdata_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            app = AppData.from_dict(data)
            if app.profiles:
                if not app.active_profile_id or \
                        app.active_profile_id not in {p.id for p in app.profiles}:
                    app.active_profile_id = app.profiles[0].id
                return app
        except (OSError, json.JSONDecodeError):
            pass

    # First launch (or corrupted file): seed a default profile.
    default = _build_default_profile()
    app = AppData(
        active_profile_id=default.id,
        profiles=[default],
    )
    save_app_data(app)
    return app


def save_app_data(app: AppData) -> None:
    path = appdata_path()
    try:
        path.write_text(
            json.dumps(app.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        # Don't crash the UI if disk is full; user can retry.
        pass
