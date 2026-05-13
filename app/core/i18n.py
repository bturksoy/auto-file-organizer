"""Translation lookup with auto-discovery from resources/i18n/*.json."""
from __future__ import annotations

import json
from pathlib import Path

from app.core.utils import resources_dir

DEFAULT_LANG = "en"


def _load_bundles() -> tuple[dict[str, str], dict[str, dict]]:
    languages: dict[str, str] = {}
    strings: dict[str, dict] = {}
    i18n_dir = resources_dir() / "i18n"
    if not i18n_dir.is_dir():
        return languages, strings
    for path in sorted(i18n_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        meta = data.get("_meta") or {}
        code = meta.get("code") or path.stem
        languages[code] = meta.get("name") or code.upper()
        strings[code] = data.get("strings", {}) or {}
    return languages, strings


class _I18N:
    def __init__(self) -> None:
        self._languages, self._strings = _load_bundles()
        if DEFAULT_LANG not in self._strings:
            self._strings.setdefault(DEFAULT_LANG, {})
            self._languages.setdefault(DEFAULT_LANG, "English")
        self._lang = DEFAULT_LANG

    @property
    def lang(self) -> str:
        return self._lang

    @property
    def languages(self) -> dict[str, str]:
        return dict(self._languages)

    def set_language(self, code: str) -> None:
        if code in self._languages:
            self._lang = code

    def t(self, key: str, **kwargs) -> str:
        table = self._strings.get(self._lang) or {}
        text = table.get(key)
        if text is None:
            text = (self._strings.get(DEFAULT_LANG) or {}).get(key, key)
        return text.format(**kwargs) if kwargs else text


i18n = _I18N()
