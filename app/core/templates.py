"""Profile templates — preset bundles users can pick when creating a profile.

Each template is a function that returns a fully-formed Profile. They share
common defaults (the bundled category set) but differ in name and rules.
"""
from __future__ import annotations

import uuid

from app.core.models import Action, Condition, Profile, Rule
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


PROFILE_TEMPLATES = {
    "empty": ("Empty (no rules)", empty),
    "downloads": ("Downloads cleanup", downloads),
}


def template_choices() -> list[tuple[str, str]]:
    """[(key, label), …] for use in a dropdown."""
    return [(k, label) for k, (label, _fn) in PROFILE_TEMPLATES.items()]


def build_from_template(key: str, name: str) -> Profile:
    if key not in PROFILE_TEMPLATES:
        return empty(name)
    _, fn = PROFILE_TEMPLATES[key]
    return fn(name)
