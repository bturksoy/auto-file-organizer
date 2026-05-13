"""Auto-update: GitHub release polling, download, swap-and-restart helper."""
from __future__ import annotations

import json
import re
import ssl
import subprocess
import sys
import urllib.request
from pathlib import Path

from app.core.utils import human_size  # noqa: F401  re-exported below

APP_VERSION = "2.7.0"
UPDATE_API_URL = (
    "https://api.github.com/repos/bturksoy/auto-file-organizer/releases/latest"
)
HTTP_TIMEOUT_S = 8


def _ssl_context() -> ssl.SSLContext:
    """Prefer the Windows trust store; fall back to certifi, then default."""
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        pass
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    return ssl.create_default_context()


def is_running_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _version_tuple(v: str) -> tuple:
    parts = []
    for chunk in (v or "").lstrip("v").split("."):
        digits = re.match(r"\d+", chunk)
        parts.append(int(digits.group()) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(remote: str, local: str) -> bool:
    return _version_tuple(remote) > _version_tuple(local)


def fetch_latest_release() -> dict | None:
    try:
        req = urllib.request.Request(
            UPDATE_API_URL,
            headers={
                "User-Agent": f"FileOrganizer/{APP_VERSION}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S,
                                    context=_ssl_context()) as r:
            data = json.load(r)
    except Exception:
        return None

    tag = (data.get("tag_name") or "").strip()
    if not tag:
        return None
    exe = next(
        (a for a in data.get("assets", [])
         if a.get("name", "").lower().endswith(".exe")),
        None,
    )
    if not exe:
        return None
    return {
        "version": tag.lstrip("v"),
        "url": exe["browser_download_url"],
        "size": exe.get("size", 0),
        "page": data.get("html_url"),
    }


def download_and_swap(asset_url: str,
                      progress_cb=None) -> None:
    """Download new exe and spawn a swap-and-restart batch.

    Does NOT exit the process — the caller must arrange a clean shutdown
    so the running exe releases its file lock.
    """
    if not is_running_frozen():
        raise RuntimeError("Auto-update only works from the packaged exe.")

    current = Path(sys.executable).resolve()
    new_path = current.with_name(current.stem + ".new.exe")

    req = urllib.request.Request(
        asset_url,
        headers={"User-Agent": f"FileOrganizer/{APP_VERSION}"},
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S * 4,
                                context=_ssl_context()) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(new_path, "wb") as out:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if progress_cb and total:
                    progress_cb(done, total)

    bat = current.with_name("_fo_update.bat")
    script = (
        '@echo off\r\n'
        'setlocal\r\n'
        'set /a RETRIES=40\r\n'
        'ping 127.0.0.1 -n 4 >nul 2>&1\r\n'
        ':loop\r\n'
        f'move /y "{new_path}" "{current}" >nul 2>&1\r\n'
        f'if not exist "{new_path}" goto done\r\n'
        'set /a RETRIES=RETRIES-1\r\n'
        'if %RETRIES% LEQ 0 goto done\r\n'
        'ping 127.0.0.1 -n 2 >nul 2>&1\r\n'
        'goto loop\r\n'
        ':done\r\n'
        f'if exist "{current}" start "" "{current}"\r\n'
        '(goto) 2>nul & del "%~f0"\r\n'
    )
    bat.write_text(script, encoding="ascii")

    subprocess.Popen(
        ["cmd.exe", "/c", str(bat)],
        creationflags=0x08000000,  # CREATE_NO_WINDOW
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
