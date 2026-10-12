"""Where things live on this computer, plus small helpers shared by the command
line and the dashboard. No Streamlit in here, so `chase-import doctor` and
`chase-import backup` can use it too.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from glob import glob
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

PROJECT_DIR = Path(__file__).resolve().parents[2]  # src/chase_import/env.py -> project folder
ENV_FILE = PROJECT_DIR / ".env"
BACKUP_DIR = PROJECT_DIR / "backups"

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"

API_KEY_NAME = "ANTHROPIC_API_KEY"
PLACEHOLDER = "sk-ant-your-key-here"  # what .env.example has, which isn't a real key


# ---------------------------------------------------------------- API key


def looks_like_api_key(key: str) -> bool:
    return key.startswith("sk-ant-") and key != PLACEHOLDER and " " not in key


def api_key_ready(env_file: Path = ENV_FILE) -> bool:
    """True when a real-looking key is set.

    If it isn't loaded yet, this reads .env again, so a key added while the
    dashboard is running works without a restart.
    """
    if looks_like_api_key(os.environ.get(API_KEY_NAME, "")):
        return True
    from dotenv import dotenv_values

    key = (dotenv_values(env_file).get(API_KEY_NAME) or "").strip() if env_file.exists() else ""
    if looks_like_api_key(key):
        os.environ[API_KEY_NAME] = key  # so Categorize can use it right away
        return True
    return False


def save_api_key(key: str, env_file: Path = ENV_FILE) -> None:
    """Write the key into .env, replacing an old one and keeping every other line."""
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    new_line = f"{API_KEY_NAME}={key}"
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{API_KEY_NAME}="):
            lines[i] = new_line
            break
    else:  # no ANTHROPIC_API_KEY line yet
        lines.append(new_line)
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[API_KEY_NAME] = key


# ---------------------------------------------------------------- Postgres tools


def _version_key(path: str) -> list[int]:
    """Sort key: the numbers in a path, so .../PostgreSQL/17/bin beats .../16/bin."""
    if "latest" in path:  # Postgres.app's Versions/latest
        return [10_000]
    return [int(n) for n in re.findall(r"\d+", path)] or [0]


def find_pg_tool(name: str) -> Path | None:
    """Find a Postgres program like pg_dump, even when it isn't on the PATH.

    Installers put these in their own folders: C:\\Program Files\\PostgreSQL\\<n>\\bin
    on Windows; Postgres.app or Homebrew folders on a Mac. When there are several,
    the newest version wins (pg_dump must be at least as new as the server).
    """
    on_path = shutil.which(name)
    if on_path:
        return Path(on_path)

    exe = name + (".exe" if IS_WINDOWS else "")
    if IS_WINDOWS:
        roots = {os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramW6432", "")}
        patterns = [str(Path(root) / "PostgreSQL" / "*" / "bin" / exe) for root in roots if root]
    else:
        patterns = [
            f"/Applications/Postgres.app/Contents/Versions/*/bin/{exe}",
            f"/opt/homebrew/opt/postgresql@*/bin/{exe}",  # Homebrew on Apple Silicon
            f"/usr/local/opt/postgresql@*/bin/{exe}",  # Homebrew on Intel Macs
            f"/opt/homebrew/bin/{exe}",
            f"/usr/local/bin/{exe}",
            f"/Library/PostgreSQL/*/bin/{exe}",  # the EDB installer on a Mac
            f"/usr/lib/postgresql/*/bin/{exe}",  # Linux
        ]
    found = [match for pattern in patterns for match in glob(pattern)]
    return Path(max(found, key=_version_key)) if found else None


def redact(url: str) -> str:
    """A database URL with the password hidden, safe to print."""
    parts = urlsplit(url)
    if "@" not in parts.netloc:
        return url
    userinfo, host = parts.netloc.rsplit("@", 1)
    if ":" not in userinfo:
        return url  # no password in it
    user = userinfo.split(":", 1)[0]
    return urlunsplit(parts._replace(netloc=f"{user}:****@{host}"))


# ---------------------------------------------------------------- the desktop


def _windows_desktop() -> Path | None:
    """Ask Windows where the Desktop is: the same call PowerShell's GetFolderPath uses.

    The Desktop isn't always C:\\Users\\<you>\\Desktop: OneDrive often moves it.
    """
    import ctypes
    import uuid

    class GUID(ctypes.Structure):
        _fields_ = [("data", ctypes.c_ubyte * 16)]

    desktop_id = GUID.from_buffer_copy(uuid.UUID("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}").bytes_le)
    path = ctypes.c_wchar_p()
    try:
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(desktop_id), 0, None, ctypes.byref(path)) != 0:
            return None
        return Path(path.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(path)


def desktop_dir() -> Path:
    """The real desktop folder."""
    if IS_WINDOWS:
        try:
            found = _windows_desktop()
            if found:
                return found
        except (OSError, AttributeError):
            pass
        # Fallback: the usual OneDrive spots, then the plain one
        for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
            if os.environ.get(var) and (Path(os.environ[var]) / "Desktop").is_dir():
                return Path(os.environ[var]) / "Desktop"
    return Path.home() / "Desktop"


def launcher_path() -> Path:
    """Where `chase-import shortcut` puts the desktop launcher."""
    name = "Spending Dashboard.lnk" if IS_WINDOWS else "Spending Dashboard.command"
    return desktop_dir() / name
