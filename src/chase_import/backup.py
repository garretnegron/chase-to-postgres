"""Back up the whole database into one file, with Postgres's own pg_dump.

A backup holds everything that lives only in the database: your categories,
manual fixes and Claude's answers, as well as the transactions. Restore one with
pg_restore (see "Backups" in the README).
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from chase_import.env import BACKUP_DIR, find_pg_tool


class BackupError(RuntimeError):
    """The backup couldn't be made. The message says why, in plain words."""


def make_backup(database_url: str, folder: Path = BACKUP_DIR) -> Path:
    """Save a backup like backups/finances-2026-10-12-1430.dump and return its path."""
    pg_dump = find_pg_tool("pg_dump")
    if pg_dump is None:
        raise BackupError(
            "Couldn't find pg_dump, the backup program that comes with PostgreSQL. "
            "Is PostgreSQL installed on this computer?"
        )

    folder.mkdir(parents=True, exist_ok=True)
    name = urlsplit(database_url).path.lstrip("/") or "database"
    out = folder / f"{name}-{datetime.now():%Y-%m-%d-%H%M%S}.dump"

    result = subprocess.run(
        [str(pg_dump), "--format=custom", f"--file={out}", f"--dbname={database_url}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        out.unlink(missing_ok=True)  # don't leave a half-written file behind
        detail = result.stderr.strip() or "pg_dump stopped with an error."
        if "version mismatch" in detail:
            detail += (" (The pg_dump found is older than the database: install the "
                       "matching PostgreSQL version's tools.)")
        raise BackupError(detail)
    return out


def list_backups(folder: Path = BACKUP_DIR) -> list[Path]:
    """Backups in the folder, newest first."""
    if not folder.is_dir():
        return []
    return sorted(folder.glob("*.dump"), key=lambda p: p.stat().st_mtime, reverse=True)
