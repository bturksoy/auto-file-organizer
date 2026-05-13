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
from app.core.models import (
    Action, Category, Condition, ConditionGroup, ContentPattern, Profile, Rule,
)
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
    meta = FileMeta(
        name=path.name,
        name_norm=normalize(path.name),
        ext=path.suffix.lower(),
        size_bytes=size,
        mtime=mtime,
        parent_norm=normalize(str(path.parent)),
    )
    # Stash the original Path so content-pattern conditions can read the file
    # without us having to round-trip the string back.
    meta._orig_path = path  # type: ignore[attr-defined]
    return meta


def _evaluate_condition(c: Condition, m: FileMeta,
                        profile: Profile | None = None) -> bool:
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
    if c.type in ("modified_after", "modified_before"):
        try:
            cutoff = datetime.fromisoformat(needle).timestamp()
        except (TypeError, ValueError):
            return False
        return (m.mtime > cutoff if c.type == "modified_after"
                else m.mtime < cutoff)
    if c.type == "content_matches":
        if profile is None:
            return False
        pattern = next(
            (p for p in profile.content_patterns if p.id == needle), None)
        if pattern is None:
            return False
        return _match_content_pattern(pattern, m)
    return False


def _evaluate_group(group: ConditionGroup, m: FileMeta,
                    profile: Profile | None = None) -> bool:
    if not group.items:
        return False
    op = group.operator
    results = (
        _evaluate_group(item, m, profile) if isinstance(item, ConditionGroup)
        else _evaluate_condition(item, m, profile)
        for item in group.items
    )
    return any(results) if op == "or" else all(results)


def _rule_matches(rule: Rule, m: FileMeta,
                  profile: Profile | None = None) -> bool:
    if not rule.enabled:
        return False
    # Prefer the new tree representation when present; otherwise fall back
    # to the flat AND list of conditions for legacy profiles.
    if rule.condition_root is not None:
        return _evaluate_group(rule.condition_root, m, profile)
    if not rule.conditions:
        return False
    return all(_evaluate_condition(c, m, profile) for c in rule.conditions)


def _match_content_pattern(pattern: ContentPattern, m: FileMeta) -> bool:
    """Run a user-defined keyword match against the file's text content."""
    ext = m.ext
    if ext not in (".pdf", ".docx"):
        return False
    path = Path(m.parent_norm) / m.name  # parent_norm is normalized; rebuild
    # Easier: use the original path. _file_meta lost the original — but
    # callers always pass FileMeta built from a real Path. Reconstruct
    # using the directory from disk lookup instead.
    # Pragmatic: caller path is the only thing we have. We stash it on
    # meta as `_orig_path` from _file_meta below to keep this clean.
    real = getattr(m, "_orig_path", None)
    if real is None:
        return False
    try:
        st = real.stat()
    except OSError:
        return False
    if ext == ".pdf":
        text = read_pdf_text_cached(str(real), st.st_mtime, st.st_size)
    else:
        text = read_docx_text_cached(str(real), st.st_mtime, st.st_size)
    if not text:
        return False
    n_text = normalize(text)
    strong_norms = [normalize(k) for k in pattern.strong]
    weak_norms = [normalize(k) for k in pattern.weak]
    if any(k in n_text for k in strong_norms):
        return True
    return sum(1 for k in weak_norms if k in n_text) >= pattern.weak_threshold


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
             ) -> tuple[Action | None, str, bool]:
    """Return (Action, reason, is_copy).

    Action is None when the file should be left alone (skipped).
    is_copy comes from the matched rule (False for category fallthrough).
    """
    mode = profile.settings.organization_mode
    m = _file_meta(path)

    # 1. Rules (skipped in categories_only)
    if mode != "categories_only":
        for rule in profile.rules:
            if _rule_matches(rule, m, profile):
                return rule.action, f"rule: {rule.name}", rule.is_copy
        if mode == "rules_only":
            return None, "no rule matched", False

    # 2. Extension-based categories
    cat = _category_for_extension(profile, m.ext)
    if cat:
        return (
            Action(type="move_to_category", target=cat.id),
            f"ext {m.ext}",
            False,
        )

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
                        False,
                    )
            except OSError:
                pass

    # 4. Fall back to the "other" category if present, otherwise skip.
    other = _category_by_id(profile, "other")
    if other:
        return (
            Action(type="move_to_category", target=other.id),
            "fallback",
            False,
        )
    return None, "no match", False


def _renamed_filename(action: Action, src: Path, m: FileMeta) -> str:
    """Apply action.rename_template to the destination filename if set."""
    template = (action.rename_template or "").strip()
    if not template:
        return src.name
    dt = datetime.fromtimestamp(m.mtime)
    tokens = {
        "stem": src.stem,
        "name": src.name,
        "ext": src.suffix,            # includes the dot, like ".pdf"
        "year": f"{dt:%Y}",
        "month": f"{dt:%m}",
        "day": f"{dt:%d}",
    }
    out = template
    for key, value in tokens.items():
        out = out.replace("{" + key + "}", value)
    return out


def resolve_destination(profile: Profile, src: Path,
                        action: Action | None) -> Path | None:
    """Translate an Action into an absolute destination path.

    Supports {year}/{month}/{day}/{ext}/{category} placeholders in the
    target folder. The destination filename can be templated via the
    action's rename_template (tokens: {stem} {ext} {name} {year} {month}
    {day}).
    """
    if action is None:
        return None
    m = _file_meta(src)
    filename = _renamed_filename(action, src, m)

    if action.type == "move_to_folder":
        folder = action.target.strip()
        if not folder:
            return None
        return Path(expand_placeholders(folder, src, m)) / filename

    if action.type == "move_to_category":
        cat = _category_by_id(profile, action.target)
        if not cat:
            return None
        leaf = expand_placeholders(
            cat.target_folder or cat.name, src, m, category=cat)
        base = profile.settings.destination_folder.strip()
        if base:
            return Path(expand_placeholders(base, src, m)) / leaf / filename
        return src.parent / leaf / filename

    return None


def category_folder_names(profile: Profile) -> set[str]:
    """All folder names we'd treat as 'own subfolders' during a scan."""
    names = set()
    for cat in profile.categories:
        for n in (cat.name, cat.target_folder):
            if n:
                names.add(n)
    return names
