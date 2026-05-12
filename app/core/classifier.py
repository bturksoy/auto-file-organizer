"""Decide which category a file belongs to under a given profile.

The classification waterfall depends on the profile's organization_mode:

  rules_then_categories  - rules first, then categories, then content scan
                           on PDFs/DOCX for a "CV" bucket, then "Other"
  rules_only             - only matched rules win; unmatched files skipped
  categories_only        - skip rules, jump straight to extensions
"""
from __future__ import annotations

import re
from pathlib import Path

from app.core.content import cv_signals, read_docx_text_cached, read_pdf_text_cached
from app.core.models import Action, Category, Condition, Profile, Rule
from app.core.normalize import normalize


def _evaluate_condition(c: Condition, name: str, name_norm: str,
                        ext: str, size_bytes: int) -> bool:
    needle = (c.value or "").strip()
    if not needle and c.type not in ("size_above_mb", "size_below_mb"):
        return False
    if c.type == "name_contains":
        return normalize(needle) in name_norm
    if c.type == "name_starts_with":
        return name_norm.startswith(normalize(needle))
    if c.type == "name_ends_with":
        return name_norm.endswith(normalize(needle))
    if c.type == "name_regex":
        try:
            return bool(re.search(needle, name, re.IGNORECASE))
        except re.error:
            return False
    if c.type == "extension_is":
        value = needle.lower().lstrip(".")
        target = ext.lstrip(".")
        return value == target
    if c.type == "size_above_mb":
        try:
            threshold = float(needle) * 1024 * 1024
            return size_bytes > threshold
        except (TypeError, ValueError):
            return False
    if c.type == "size_below_mb":
        try:
            threshold = float(needle) * 1024 * 1024
            return size_bytes < threshold
        except (TypeError, ValueError):
            return False
    return False


def _rule_matches(rule: Rule, name: str, name_norm: str, ext: str,
                  size_bytes: int) -> bool:
    if not rule.enabled or not rule.conditions:
        return False
    # All conditions must hold (AND). UIs that need OR can splice multiple rules.
    return all(
        _evaluate_condition(c, name, name_norm, ext, size_bytes)
        for c in rule.conditions
    )


def _category_for_extension(profile: Profile, ext: str) -> Category | None:
    for cat in profile.categories:
        if not cat.enabled:
            continue
        if ext in {e.lower() for e in cat.extensions}:
            return cat
    return None


def _category_by_id(profile: Profile, category_id: str) -> Category | None:
    for cat in profile.categories:
        if cat.id == category_id:
            return cat
    return None


def classify(profile: Profile, path: Path,
             inspect_content: bool = True
             ) -> tuple[Action, str]:
    """Return (Action, reason). Caller resolves the destination.

    Action.type is "move_to_category" with target=category_id, or
    "move_to_folder" with target=absolute path, or "skip".
    """
    mode = profile.settings.organization_mode
    name = path.name
    name_norm = normalize(name)
    ext = path.suffix.lower()
    try:
        size_bytes = path.stat().st_size
    except OSError:
        size_bytes = 0

    # 1. Rules (skipped in categories_only)
    if mode != "categories_only":
        for rule in profile.rules:
            if _rule_matches(rule, name, name_norm, ext, size_bytes):
                return rule.action, f"rule: {rule.name}"
        if mode == "rules_only":
            return Action(type="skip"), "no rule matched"

    # 2. Extension-based categories
    cat = _category_for_extension(profile, ext)
    if cat:
        return Action(type="move_to_category", target=cat.id), f"ext {ext}"

    # 3. Content inspection for PDF/DOCX (only when we still don't know
    # what the file is). Files that look like a CV go to the CV category.
    if inspect_content and ext in (".pdf", ".docx"):
        cv_cat = _category_by_id(profile, "cv")
        if cv_cat and cv_cat.enabled:
            try:
                st = path.stat()
                text = (
                    read_pdf_text_cached(str(path), st.st_mtime, st.st_size)
                    if ext == ".pdf"
                    else read_docx_text_cached(str(path), st.st_mtime, st.st_size)
                )
                strong, weak = cv_signals(text)
                if strong or len(weak) >= 2:
                    label = "strong" if strong else f"weak x{len(weak)}"
                    return (
                        Action(type="move_to_category", target=cv_cat.id),
                        f"content {label}",
                    )
            except OSError:
                pass

    # 4. Fall back to the "other" category if present, otherwise skip.
    other = _category_by_id(profile, "other")
    if other:
        return Action(type="move_to_category", target=other.id), "fallback"
    return Action(type="skip"), "no match"


def resolve_destination(profile: Profile, src: Path,
                        action: Action) -> Path | None:
    """Translate an Action into an absolute destination path."""
    if action.type == "skip":
        return None
    if action.type == "move_to_folder":
        folder = action.target.strip()
        if not folder:
            return None
        return Path(folder) / src.name
    if action.type == "move_to_category":
        cat = _category_by_id(profile, action.target)
        if not cat:
            return None
        base = profile.settings.destination_folder.strip()
        if base:
            return Path(base) / (cat.target_folder or cat.name) / src.name
        return src.parent / (cat.target_folder or cat.name) / src.name
    return None


def category_folder_names(profile: Profile) -> set[str]:
    """All folder names we'd treat as 'own subfolders' during a scan."""
    names = set()
    for cat in profile.categories:
        for n in (cat.name, cat.target_folder):
            if n:
                names.add(n)
    return names
