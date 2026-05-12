"""Profile templates — preset bundles users can pick when creating a profile.

Each template is a function that returns a fully-formed Profile. They share
common defaults (the bundled category set) but differ in name, rules, and
profile-level settings.
"""
from __future__ import annotations

import uuid

from app.core.models import Action, Category, Condition, Profile, ProfileSettings, Rule
from app.core.storage import _build_default_profile


def _seed_profile(name: str) -> Profile:
    """Start from the bundled defaults but with a custom name and fresh id."""
    p = _build_default_profile()
    p.id = uuid.uuid4().hex
    p.name = name
    return p


def empty(name: str = "New profile") -> Profile:
    """A profile with no rules; default extension categories."""
    return _seed_profile(name)


def downloads(name: str = "Downloads") -> Profile:
    """Geared at a messy Downloads folder: keep it tidy in place."""
    p = _seed_profile(name)
    p.settings.recursive_scan = False
    p.settings.inspect_pdf_docx = True
    p.rules = [
        Rule(
            id=uuid.uuid4().hex, name="Setup installers", enabled=True,
            conditions=[Condition(type="name_starts_with", value="setup_")],
            action=Action(type="move_to_category", target="installers"),
        ),
        Rule(
            id=uuid.uuid4().hex, name="Screenshots by month",
            enabled=True,
            conditions=[Condition(type="name_starts_with", value="Screenshot")],
            action=Action(type="move_to_folder",
                          target="Screenshots/{year}-{month}"),
        ),
    ]
    return p


def photo_library(name: str = "Photo library") -> Profile:
    """Camera-style imports: bucket by year/month under a chosen library."""
    p = _seed_profile(name)
    p.settings.recursive_scan = True
    p.settings.inspect_pdf_docx = False
    # Replace generic image category target with year/month bucketing.
    for cat in p.categories:
        if cat.id == "images":
            cat.target_folder = "Photos/{year}/{month}"
    p.rules = [
        Rule(
            id=uuid.uuid4().hex, name="RAW originals", enabled=True,
            conditions=[Condition(type="extension_in",
                                  value=".raw, .cr2, .nef, .arw")],
            action=Action(type="move_to_folder",
                          target="Photos/RAW/{year}/{month}"),
        ),
    ]
    return p


def documents_library(name: str = "Documents") -> Profile:
    """Centralize PDFs/DOCX into a paperwork vault by year."""
    p = _seed_profile(name)
    p.settings.recursive_scan = False
    p.settings.inspect_pdf_docx = True
    for cat in p.categories:
        if cat.id in ("documents", "spreadsheets", "presentations"):
            cat.target_folder = f"{cat.name}/{{year}}"
        if cat.id == "cv":
            cat.target_folder = "CVs"
    return p


def archive_keeper(name: str = "Archive") -> Profile:
    """A copy-only profile that mirrors classified files to another tree."""
    p = _seed_profile(name)
    p.settings.recursive_scan = True
    # No move actions — everything copies. Convert each category-based rule
    # to its copy equivalent by default. (Categories themselves still move;
    # the rule layer wins first because mode is rules-then-categories.)
    p.rules = [
        Rule(
            id=uuid.uuid4().hex, name="Mirror everything to /Archive",
            enabled=True,
            conditions=[Condition(type="name_contains", value="")],  # match all
            action=Action(type="copy_to_folder",
                          target="Archive/{year}/{month}"),
        ),
    ]
    return p


PROFILE_TEMPLATES = {
    "empty": ("Empty (no rules)", empty),
    "downloads": ("Downloads cleanup", downloads),
    "photos": ("Photo library (year/month)", photo_library),
    "documents": ("Documents vault (by year)", documents_library),
    "archive": ("Archive mirror (copy only)", archive_keeper),
}


def template_choices() -> list[tuple[str, str]]:
    """[(key, label), …] for use in a dropdown."""
    return [(k, label) for k, (label, _fn) in PROFILE_TEMPLATES.items()]


def build_from_template(key: str, name: str) -> Profile:
    if key not in PROFILE_TEMPLATES:
        return empty(name)
    _, fn = PROFILE_TEMPLATES[key]
    return fn(name)
