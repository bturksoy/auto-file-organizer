"""Duplicate-file detection.

Two-pass strategy to avoid hashing every file in a large folder:

  1. Group files by `(size, suffix)`. Anything alone in its bucket is
     unique by definition (different size means different content).
  2. For each non-singleton bucket, compute the SHA-256 hash of the
     contents in 1 MiB chunks. Files with identical hashes are
     duplicates.

We deliberately stick to byte-identical detection. Perceptual hashing
for images would be nicer but pulls in a heavy dependency tree; this
covers the 95% case (saved-twice PDFs, duplicate downloads, "(1)"
copies from browsers).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from app.core.utils import human_size as _human_size


_CHUNK = 1024 * 1024  # 1 MiB
_SKIP_NAMES = {"Thumbs.db", "desktop.ini", ".DS_Store"}


@dataclass
class DuplicateFile:
    path: Path
    size: int
    mtime: float


@dataclass
class DuplicateGroup:
    """A set of files that share the same SHA-256."""
    hash_hex: str
    size: int
    files: list[DuplicateFile]

    @property
    def wasted_bytes(self) -> int:
        """How much disk space would be reclaimed by keeping one copy."""
        return self.size * max(0, len(self.files) - 1)


def _iter_files(folder: Path, recursive: bool) -> Iterable[Path]:
    if recursive:
        for p in folder.rglob("*"):
            if p.is_file() and p.name not in _SKIP_NAMES:
                yield p
    else:
        for p in folder.iterdir():
            if p.is_file() and p.name not in _SKIP_NAMES:
                yield p


def _hash_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            while True:
                chunk = f.read(_CHUNK)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def find_duplicates(folder: Path, recursive: bool = False,
                    progress_cb: Callable[[int, int], None] | None = None
                    ) -> list[DuplicateGroup]:
    """Return all groups of byte-identical files in `folder`.

    Singleton groups (only one file) are omitted. Groups are sorted by
    wasted bytes desc so the highest-impact dupes surface first.
    """
    # Pass 1: bucket by size to skip the expensive hashing for uniques.
    buckets: dict[tuple[int, str], list[Path]] = {}
    all_files: list[Path] = []
    for p in _iter_files(folder, recursive):
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size == 0:
            continue
        buckets.setdefault((size, p.suffix.lower()), []).append(p)
        all_files.append(p)

    candidates: list[Path] = []
    for paths in buckets.values():
        if len(paths) >= 2:
            candidates.extend(paths)

    # Pass 2: hash the candidates.
    groups: dict[str, list[DuplicateFile]] = {}
    total = len(candidates)
    for i, path in enumerate(candidates, start=1):
        if progress_cb is not None:
            progress_cb(i, total)
        h = _hash_file(path)
        if h is None:
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        groups.setdefault(h, []).append(
            DuplicateFile(path=path, size=st.st_size, mtime=st.st_mtime))

    out: list[DuplicateGroup] = []
    for h, files in groups.items():
        if len(files) >= 2:
            # Stable sort: keep the oldest (most likely the "original") first.
            files.sort(key=lambda f: f.mtime)
            out.append(DuplicateGroup(
                hash_hex=h, size=files[0].size, files=files))
    out.sort(key=lambda g: g.wasted_bytes, reverse=True)
    return out


# Re-exported for callers that already import duplicates.human_size.
human_size = _human_size
