"""Count how many files in a folder would be caught by each rule.

The Rules page uses these counts to render live "X matched" chips on each
card. The scan is intentionally cheap: it does not consult PDF content,
recurses only when the profile is configured to, and uses the same
classifier evaluation a real organize run would.
"""
from __future__ import annotations

from pathlib import Path

from app.core.classifier import _file_meta, _rule_matches
from app.core.models import Profile
from app.core.organize import DEFAULT_SKIP_NAMES


def count_matches(root: Path, profile: Profile) -> dict[str, int]:
    """Return {rule_id: count} for files in *root*.

    Files are counted toward the FIRST rule they match (mirroring how
    organize behaves), so the totals add up to <= the number of files
    scanned. Skipped files (dotfiles, the undo log) don't count.
    """
    if not root.is_dir():
        return {r.id: 0 for r in profile.rules}

    skip = DEFAULT_SKIP_NAMES | {
        # Treat all known category folder names as own-managed dirs.
        c.target_folder or c.name for c in profile.categories
    }

    counts = {r.id: 0 for r in profile.rules}
    if not profile.rules:
        return counts

    def walk(base: Path) -> None:
        try:
            entries = list(base.iterdir())
        except OSError:
            return
        for entry in entries:
            name = entry.name
            if entry.is_dir():
                if (profile.settings.recursive_scan
                        and name not in skip
                        and not name.startswith(".")):
                    walk(entry)
                continue
            if name in DEFAULT_SKIP_NAMES or name.startswith("."):
                continue
            meta = _file_meta(entry)
            for rule in profile.rules:
                if _rule_matches(rule, meta):
                    counts[rule.id] += 1
                    break

    walk(root)
    return counts
