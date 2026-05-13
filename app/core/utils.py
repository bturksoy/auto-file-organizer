"""Shared helpers that used to live in 3+ copies across the codebase.

`resources_dir()` — locate the bundled resources folder whether we're
running from source or from a PyInstaller --onefile bundle.

`human_size(n)` — format a byte count for display. Used by the stats
dialog, duplicate finder, update prompt, and plan preview pane.
"""
from __future__ import annotations

import sys
from pathlib import Path


def resources_dir() -> Path:
    """Path to the bundled resources directory (icons, i18n, data)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "resources"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2] / "resources"


def human_size(n: int | float) -> str:
    """Render a byte count as KB / MB / GB. Single-source of truth."""
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(n)} B"
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
