"""Decide which category a file belongs to under a given profile.

The classification waterfall depends on the profile's organization_mode:

  rules_then_categories  - rules first, then categories, then content scan
                           on PDFs/DOCX for a "CV" bucket, then "Other"
  rules_only             - only matched rules win; unmatched files skipped
  categories_only        - skip rules, jump straight to extensions
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.core.content import cv_signals, read_docx_text_cached, read_pdf_text_cached
from app.core.models import Action, Category, Condition, Profile, Rule
from app.core.normalize import normalize


@dataclass
class FileMeta:
    """Bundled info about a file used by condition evaluation."""
    name: str
    name_norm: str
    ext: str                # ".pdf"
    size_bytes: int
    mtime: float            # epoch seconds
    parent_norm: str        # normalized parent folder path


def _file_meta(path: Path) -> FileMeta:
    try:
        st = path.stat()
        size = st.st_size
        mtime = st.st_mtime
    except OSError:
        size = 0
        mtime = time.time()
    return FileMeta(
        name=path.name,
        name_norm=normalize(path.name),
        ext=path.suffix.lower(),
        size_bytes=size,
        mtime=mtime,
        parent_norm=normalize(str(path.parent)),
    )


def _evaluate_condition(c: Condition, m: FileMeta) -> bool:
    needle = (c.value or "").strip()
    numeric_types = {"size_above_mb", "size_below_mb",
                     "age_above_days", "age_below_days"}
    if not needle and c.type not in numeric_types:
        return False

    if c.type == "name_contains":
        return normalize(needle) in m.name_norm
    if c.type == "name_does_not_contain":
        return normalize(needle) not in m.name_norm
    if c.type == "name_starts_with":
        return m.name_norm.startswith(normalize(needle))
    if c.type == "name_ends_with":
        return m.name_norm.endswith(normalize(needle))
    if c.type == "name_regex":
        try:
            return bool(re.search(needle, m.name, re.IGNORECASE))
        except re.error:
            return False
    if c.type == "extension_is":
        return needle.lower().lstrip(".") == m.ext.lstrip(".")
    if c.type == "extension_in":
        # value is comma- or space- separated list of extensions
        wanted = {
            tok.lower().lstrip(".")
            for tok in re.split(r"[,\s]+", needle)
            if tok
        }
        return m.ext.lstrip(".") in wanted
    if c.type == "path_contains":
        return normalize(needle) in m.parent_norm
    if c.type == "size_above_mb":
        try:
            return m.size_bytes > float(needle) * 1024 * 1024
        except (TypeError, ValueError):
            return False
    if c.type == "size_below_mb":
        try:
            return m.size_bytes < float(needle) * 1024 * 1024
        except (TypeError, ValueError):
            return False
    if c.type in ("age_above_days", "age_below_days"):
        try:
            days = float(needle)
        except (TypeError, ValueError):
            return False
        age_days = (time.time() - m.mtime) / 86400.0
        return age_days > days if c.type == "age_above_days" else age_days < days
    return False


def _rule_matches(rule: Rule, m: FileMeta) -> bool:
    if not rule.enabled or not rule.conditions:
        return False
    # All conditions must hold (AND). To express OR, split into multiple rules.
    return all(_evaluate_condition(c, m) for c in rule.conditions)


def expand_placeholders(template: str, src: Path, m: FileMeta,
                        category: Category | None = None) -> str:
    """Replace {year}/{month}/{day}/{ext}/{category} tokens using the file's mtime."""
    if "{" not in template:
        return template
    dt = datetime.fromtimestamp(m.mtime)
    repl = {
        "year": f"{dt:%Y}",
        "month": f"{dt:%m}",
        "day": f"{dt:%d}",
        "ext": m.ext.lstrip(".") or "noext",
        "category": (category.name if category else ""),
    }
    out = template
    for key, value in repl.items():
        out = out.replace("{" + key + "}", value)
    return out


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
    """Return (Action, reason). Caller resolves the destination."""
    mode = profile.settings.organization_mode
    m = _file_meta(path)

    # 1. Rules (skipped in categories_only)
    if mode != "categories_only":
        for rule in profile.rules:
            if _rule_matches(rule, m):
                return rule.action, f"rule: {rule.name}"
        if mode == "rules_only":
            return Action(type="skip"), "no rule matched"

    # 2. Extension-based categories
    cat = _category_for_extension(profile, m.ext)
    if cat:
        return Action(type="move_to_category", target=cat.id), f"ext {m.ext}"

    # 3. Content inspection for PDF/DOCX (per-profile toggle).
    if (inspect_content
            and profile.settings.inspect_pdf_docx
            and m.ext in (".pdf", ".docx")):
        cv_cat = _category_by_id(profile, "cv")
        if cv_cat and cv_cat.enabled:
            try:
                st = path.stat()
                text = (
                    read_pdf_text_cached(str(path), st.st_mtime, st.st_size)
                    if m.ext == ".pdf"
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
    """Translate an Action into an absolute destination path.

    Supports {year}/{month}/{day}/{ext}/{category} placeholders in both
    the category's target_folder and a literal folder target.
    """
    if action.type == "skip":
        return None
    m = _file_meta(src)

    if action.type in ("move_to_folder", "copy_to_folder"):
        folder = action.target.strip()
        if not folder:
            return None
        return Path(expand_placeholders(folder, src, m)) / src.name

    if action.type in ("move_to_category", "copy_to_category"):
        cat = _category_by_id(profile, action.target)
        if not cat:
            return None
        leaf = expand_placeholders(
            cat.target_folder or cat.name, src, m, category=cat)
        base = profile.settings.destination_folder.strip()
        if base:
            return Path(expand_placeholders(base, src, m)) / leaf / src.name
        return src.parent / leaf / src.name

    return None


def is_copy_action(action: Action) -> bool:
    return action.type in ("copy_to_category", "copy_to_folder")


def category_folder_names(profile: Profile) -> set[str]:
    """All folder names we'd treat as 'own subfolders' during a scan."""
    names = set()
    for cat in profile.categories:
        for n in (cat.name, cat.target_folder):
            if n:
                names.add(n)
    return names
