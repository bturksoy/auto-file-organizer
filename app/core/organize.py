"""Folder scanning, move planning, move execution, and undo."""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.core.classifier import (
    category_folder_names, classify, resolve_destination,
)
from app.core.models import Action, Profile

UNDO_LOG_NAME = ".file-organizer-undo.json"
DEFAULT_SKIP_NAMES = {
    UNDO_LOG_NAME, "desktop.ini", "Thumbs.db", "thumbs.db", "$RECYCLE.BIN",
}


@dataclass
class PlannedMove:
    src: Path
    dst: Path
    category_id: str
    reason: str

    def to_display(self, profile: Profile) -> str:
        return self.dst.parent.name or "?"


@dataclass
class OrganizeResult:
    folder: Path
    moved: int = 0
    skipped: int = 0
    errors: int = 0
    bytes_total: int = 0
    elapsed_seconds: float = 0.0
    per_category: dict[str, int] | None = None


def scan_folder(root: Path, profile: Profile,
                inspect_content: bool = True,
                progress_cb: Callable[[int, int, str], None] | None = None,
                ) -> list[PlannedMove]:
    """Walk the top level of *root* and produce a move plan."""
    skip_dirs = category_folder_names(profile)
    entries: list[Path] = []
    for entry in root.iterdir():
        if entry.is_dir():
            continue
        name = entry.name
        if name in DEFAULT_SKIP_NAMES or name.startswith("."):
            continue
        if name in skip_dirs:
            continue
        entries.append(entry)

    plan: list[PlannedMove] = []
    total = len(entries)
    for i, entry in enumerate(entries, 1):
        if progress_cb:
            progress_cb(i, total, entry.name)
        action, reason = classify(profile, entry, inspect_content)
        dst = resolve_destination(profile, entry, action)
        if action.type == "skip" or dst is None:
            continue
        category_id = action.target if action.type == "move_to_category" else "_folder"
        plan.append(PlannedMove(
            src=entry, dst=dst, category_id=category_id, reason=reason,
        ))
    return plan


def _resolve_conflict(dst: Path) -> Path:
    if not dst.exists():
        return dst
    stem, suffix, parent = dst.stem, dst.suffix, dst.parent
    i = 1
    while True:
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def apply_plan(root: Path, plan: list[PlannedMove],
               on_move: Callable[[PlannedMove], None] | None = None,
               on_error: Callable[[PlannedMove, Exception], None] | None = None,
               ) -> OrganizeResult:
    """Execute a plan and record an undo entry."""
    result = OrganizeResult(folder=root, per_category={})
    started = time.monotonic()
    undo_records: list[dict] = []
    timestamp = datetime.now().isoformat(timespec="seconds")

    for move in plan:
        try:
            size = move.src.stat().st_size
        except OSError:
            size = 0
        try:
            move.dst.parent.mkdir(parents=True, exist_ok=True)
            final = _resolve_conflict(move.dst)
            shutil.move(str(move.src), str(final))
            undo_records.append({"from": str(final), "to": str(move.src)})
            result.moved += 1
            result.bytes_total += size
            result.per_category[move.category_id] = (
                result.per_category.get(move.category_id, 0) + 1
            )
            if on_move:
                on_move(move)
        except Exception as exc:  # noqa: BLE001
            result.errors += 1
            if on_error:
                on_error(move, exc)

    result.elapsed_seconds = time.monotonic() - started
    _append_undo_log(root, timestamp, undo_records)
    return result


def _append_undo_log(root: Path, timestamp: str, records: list[dict]) -> None:
    if not records:
        return
    log_path = root / UNDO_LOG_NAME
    history: list[dict] = []
    if log_path.exists():
        try:
            history = json.loads(log_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            history = []
    history.append({"timestamp": timestamp, "moves": records})
    try:
        log_path.write_text(
            json.dumps(history, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def load_undo_log(root: Path) -> list[dict]:
    try:
        return json.loads((root / UNDO_LOG_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def undo_last(root: Path) -> tuple[int, int]:
    """Reverse the most recent operation. Returns (restored, errors)."""
    history = load_undo_log(root)
    if not history:
        return 0, 0
    last = history.pop()
    moves = list(reversed(last.get("moves", [])))
    restored = 0
    errors = 0
    for m in moves:
        src = Path(m["from"])
        dst = Path(m["to"])
        try:
            if not src.exists():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(_resolve_conflict(dst)))
            restored += 1
        except Exception:
            errors += 1

    log_path = root / UNDO_LOG_NAME
    try:
        if history:
            log_path.write_text(
                json.dumps(history, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        else:
            log_path.unlink(missing_ok=True)
    except OSError:
        pass
    return restored, errors
