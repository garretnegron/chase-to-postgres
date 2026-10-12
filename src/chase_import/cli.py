"""Command line: chase-import init | load | summary | categorize | dashboard | shortcut | backup | doctor"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import parser as p

HELP = """\
Load Chase CSV / Excel / Parquet exports into Postgres.

  chase-import init                       create the tables (safe to re-run)
  chase-import load downloads/            load every export in a folder
  chase-import load file.csv --account 1234 --name "Joint checking"
  chase-import load downloads/ --dry-run  check files without touching the DB
  chase-import summary                    what's in the database
  chase-import categorize --dry-run       ask Claude about uncategorized merchants, save nothing
  chase-import categorize                 ask Claude and save the answers
  chase-import dashboard                  open the dashboard in your browser
  chase-import shortcut                   put a Spending Dashboard launcher on the desktop
  chase-import backup                     save a backup of the database into backups/
  chase-import doctor                     check the setup and say how to fix problems

The database comes from --db or DATABASE_URL (a .env file works too), e.g.
  postgresql://postgres:password@localhost:5432/finances
"""


def _db_url(args) -> str:
    url = args.db or os.environ.get("DATABASE_URL")
    if not url:
        sys.exit(
            "No database set. Put DATABASE_URL=postgresql://... in a .env file "
            "or pass --db."
        )
    return url


def _pending_note(f) -> str:
    if not f.pending_skipped:
        return ""
    return f", {f.pending_skipped} pending skipped (they'll load once posted)"


def cmd_init(args) -> None:
    from . import db

    with db.connect(_db_url(args)) as conn:
        db.init_schema(conn)
    print("Tables ready.")


def cmd_load(args) -> None:
    try:
        paths = p.find_files(args.paths)
    except FileNotFoundError as e:
        sys.exit(f"Not found: {e}")
    if not paths:
        sys.exit("No .csv, .xlsx or .parquet files found.")
    if args.account and len(paths) > 1:
        print("Note: --account applies to every file in this run.")

    parsed_files = []
    failed = False
    for path in paths:
        try:
            parsed = p.parse_file(path, account_last4=args.account)
        except p.ParseError as e:
            print(f"SKIP  {path.name}: {e}")
            failed = True
            continue
        if not parsed.account_last4:
            print(
                f"SKIP  {path.name}: can't tell which account this is from the "
                "file name. Re-run with --account 1234 (last 4 digits)."
            )
            failed = True
            continue
        parsed_files.append(parsed)

    if args.name and len({(f.account_last4, f.kind) for f in parsed_files}) > 1:
        sys.exit(
        "--name only works when every file is for the same account. "
        "Load each account's file separately to give it a name."
        )

    if args.dry_run:
        for f in parsed_files:
            ts = f.transactions
            span = f"{ts[0].posted_date} to {ts[-1].posted_date}" if ts else "empty"
            print(
                f"OK    {f.path.name}: {f.kind} ...{f.account_last4}, "
                f"{len(ts)} rows, {span}{_pending_note(f)}"
            )
        sys.exit(1 if failed else 0)

    from . import db

    with db.connect(_db_url(args)) as conn:
        db.init_schema(conn)
        total_new = 0
        for f in parsed_files:
            new, dup = db.load_file(conn, f, nickname=args.name)
            total_new += new
            print(
                f"LOAD  {f.path.name}: {new} new, {dup} already in the database "
                f"({f.kind} ...{f.account_last4}){_pending_note(f)}"
            )
    print(f"Done. {total_new} new transactions.")
    if failed:
        sys.exit(1)


def cmd_summary(args) -> None:
    from . import db

    with db.connect(_db_url(args)) as conn:
        rows = db.summary(conn)
    if not rows:
        print("Database is empty.")
        return
    for name, count, first, last in rows:
        print(f"{name:<30} {count:>7} transactions   {first} to {last}")


def cmd_categorize(args) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit(
            "No API key set. Put ANTHROPIC_API_KEY=... in a .env file. "
            "(Get one at https://platform.claude.com)."
        )

    from . import categorize, db

    with db.connect(_db_url(args)) as conn:
        found = categorize.run(conn, dry_run=args.dry_run, limit=args.limit)

    if args.dry_run:
        for merchant, sub in found.items():
            print(f"{merchant:<45} -> {sub}")

    verb = "would be" if args.dry_run else "were"
    print(f"Done. {len(found)} merchants {verb} categorized.")


DASHBOARD_URL = "http://localhost:8501"


def _dashboard_running() -> bool:
    """Is a dashboard already answering on this computer?"""
    import urllib.request

    try:
        urllib.request.urlopen(DASHBOARD_URL + "/_stcore/health", timeout=1)
        return True
    except OSError:  # nothing listening (URLError is a kind of OSError)
        return False


def cmd_dashboard(args) -> None:
    import importlib.util
    import subprocess
    import time
    import webbrowser
    from pathlib import Path

    if importlib.util.find_spec("streamlit") is None:
        sys.exit('The dashboard needs Streamlit. Install it with: pip install -e ".[dashboard]"')

    # Double-clicked twice? Don't start a second copy, just show the first one.
    if _dashboard_running():
        print("The dashboard is already running. Opening it in your browser.")
        webbrowser.open(DASHBOARD_URL)
        return

    env = os.environ.copy()
    env["DATABASE_URL"] = _db_url(args)
    script = Path(__file__).parent / "dashboard" / "app.py"
    server = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", str(script),
            "--server.address", "localhost",
            "--server.port", "8501",
            # headless: Streamlit doesn't open the browser or ask for an email on
            # first run (a question nobody would see in a minimized window).
            # We open the browser ourselves once the dashboard is ready.
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--client.toolbarMode", "minimal",  # hides "Deploy" and the developer menu
        ],
        env=env,
    )

    # Wait (up to 30 seconds) for it to answer, then open the browser.
    for _ in range(60):
        if server.poll() is not None:  # it stopped on its own: an error was printed above
            sys.exit(server.returncode or 1)
        if _dashboard_running():
            print(f"Dashboard ready at {DASHBOARD_URL}")
            webbrowser.open(DASHBOARD_URL)
            break
        time.sleep(0.5)

    try:
        server.wait()  # keep running until the window is closed or Ctrl+C
    except KeyboardInterrupt:
        server.terminate()


def cmd_shortcut(args) -> None:
    """Put a "Spending Dashboard" launcher on the desktop (Windows or Mac)."""
    from .env import IS_MAC, IS_WINDOWS, PROJECT_DIR

    if IS_WINDOWS:
        made = _windows_shortcut(PROJECT_DIR)
    elif IS_MAC:
        made = _mac_shortcut(PROJECT_DIR)
    else:
        sys.exit("The desktop shortcut is for Windows and Mac. Run `chase-import dashboard` instead.")
    print(f"Created {made}")


def _windows_shortcut(project: Path) -> str:
    import subprocess

    launcher = project / "Spending Dashboard.bat"
    icon = project / "assets" / "spending.ico"
    if not launcher.exists():
        sys.exit(f"Can't find {launcher}.")

    def quoted(path: Path) -> str:
        """A path as a PowerShell 'string' (a ' inside, as in O'Brien, is written '')."""
        return "'" + str(path).replace("'", "''") + "'"

    # Windows makes shortcuts through a built-in COM object, easiest to reach
    # from PowerShell. GetFolderPath finds the real desktop, even when OneDrive
    # has moved it. WindowStyle 7 = start minimized: the black window sits in the
    # taskbar (closing it stops the dashboard) instead of in the way.
    script = f"""
$desktop = [Environment]::GetFolderPath('Desktop')
$link = (New-Object -ComObject WScript.Shell).CreateShortcut("$desktop\\Spending Dashboard.lnk")
$link.TargetPath = {quoted(launcher)}
$link.WorkingDirectory = {quoted(project)}
$link.IconLocation = {quoted(icon)}
$link.WindowStyle = 7
$link.Description = 'Open the spending dashboard'
$link.Save()
Write-Output "$desktop\\Spending Dashboard.lnk"
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"Couldn't create the shortcut:\n{result.stderr.strip()}")
    return result.stdout.strip()


def _mac_shortcut(project: Path) -> str:
    """Write a double-clickable "Spending Dashboard.command" onto the Desktop.

    macOS opens .command files in Terminal and runs them. We write it here, on
    the Mac, instead of keeping it in git: git on Windows can't record the
    "this file may run" permission, and without it a double-click does nothing.
    """
    import json
    import shlex
    import subprocess

    from .env import launcher_path

    target = launcher_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    # sys.executable is the Python in this project's .venv. `python -m chase_import`
    # runs the same thing as the chase-import command.
    target.write_text(
        "#!/bin/bash\n"
        "# Opens the spending dashboard. Made by `chase-import shortcut`.\n"
        "# Keep this Terminal window open while you use it: closing it stops the dashboard.\n"
        f"cd {shlex.quote(str(project))} || exit 1\n"
        f"exec {shlex.quote(sys.executable)} -m chase_import dashboard\n",
        encoding="utf-8",
    )
    target.chmod(0o755)  # rwx for you, r-x for others: "this file may run"

    # Give it the blue chart icon. Best effort: a plain icon still works fine.
    png = project / "assets" / "spending.png"
    if png.exists():
        script = (
            "ObjC.import('AppKit');"
            f"var img = $.NSImage.alloc.initWithContentsOfFile({json.dumps(str(png))});"
            f"$.NSWorkspace.sharedWorkspace.setIconForFileOptions(img, {json.dumps(str(target))}, 0);"
        )
        try:
            subprocess.run(["osascript", "-l", "JavaScript", "-e", script], capture_output=True)
        except OSError:
            pass
    return str(target)


def cmd_backup(args) -> None:
    from .backup import BackupError, make_backup

    try:
        path = make_backup(_db_url(args))
    except BackupError as e:
        sys.exit(f"Backup failed: {e}")
    size = path.stat().st_size / 1024
    print(f"Saved {path} ({size:,.0f} KB)")


def cmd_doctor(args) -> None:
    """Check everything the app needs, and say how to fix what's missing."""
    import importlib.util
    import platform

    from . import env

    failures = 0

    def report(status: str, what: str, detail: str = "") -> None:
        nonlocal failures
        failures += status == "FAIL"
        # Plain-text marks: emoji can crash some Windows consoles.
        mark = {"ok": "[ ok ]", "warn": "[warn]", "FAIL": "[FAIL]", "info": "[info]"}[status]
        print(f"{mark} {what}" + (f"\n       {detail}" if detail else ""))

    print(f"chase-import doctor, on {platform.system()} {platform.release()}\n")

    # Python and packages
    if sys.version_info >= (3, 10):
        report("ok", f"Python {platform.python_version()}")
    else:
        report("FAIL", f"Python {platform.python_version()}", "Needs 3.10 or newer: install it from python.org.")
    missing = [m for m in ("pandas", "psycopg", "openpyxl", "pyarrow", "anthropic", "dotenv")
               if importlib.util.find_spec(m) is None]
    if missing:
        report("FAIL", "Packages missing: " + ", ".join(missing),
               'In the project folder, with the .venv active: pip install -e ".[dashboard]"')
    else:
        report("ok", "Packages installed")
    if importlib.util.find_spec("streamlit") is None:
        report("warn", "Streamlit isn't installed, so the dashboard won't start",
               'pip install -e ".[dashboard]"')
    else:
        report("ok", "Streamlit installed (for the dashboard)")

    # Settings file
    if env.ENV_FILE.exists():
        report("ok", f"Settings file: {env.ENV_FILE}")
    else:
        report("warn", f"No settings file at {env.ENV_FILE}",
               "Copy .env.example to .env and fill in DATABASE_URL.")

    # Database
    url = args.db or os.environ.get("DATABASE_URL")
    if not url:
        report("FAIL", "No database set", "Add a DATABASE_URL=postgresql://... line to .env.")
    else:
        try:
            import psycopg

            with psycopg.connect(url, connect_timeout=5) as conn:
                version = conn.info.server_version  # e.g. 170002 for 17.2
                report("ok" if version >= 150000 else "FAIL",
                       f"Database reachable: {env.redact(url)} (PostgreSQL {version // 10000})",
                       "" if version >= 150000 else "This app needs PostgreSQL 15 or newer.")
                tables = conn.execute("SELECT to_regclass('transactions') IS NOT NULL").fetchone()[0]
                if tables:
                    txns = conn.execute("SELECT count(*) FROM transactions").fetchone()[0]
                    cats = conn.execute("SELECT count(*) FROM categories").fetchone()[0]
                    report("info", f"{txns:,} transactions, {cats} subcategories")
                else:
                    report("info", "No tables yet: the dashboard or `chase-import init` creates them")
        except Exception as e:  # noqa: BLE001 - any failure here means "can't connect"
            first_line = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
            hint = ("Is Postgres.app running (elephant in the menu bar)? Is DATABASE_URL right?"
                    if env.IS_MAC else
                    "Is the PostgreSQL service running? Is the password in DATABASE_URL right?")
            report("FAIL", f"Can't reach the database at {env.redact(url)}", f"{first_line}\n       {hint}")

    # Claude API key
    if env.api_key_ready():
        report("ok", "Claude API key set")
    else:
        report("warn", "No Claude API key: Categorize with AI won't work",
               "Paste one on the dashboard's welcome page or Import tab.")

    # Backups
    pg_dump = env.find_pg_tool("pg_dump")
    if pg_dump:
        report("ok", f"Backup tool found: {pg_dump}")
    else:
        report("warn", "Can't find pg_dump, so backups won't work",
               "It comes with PostgreSQL; is PostgreSQL installed here?")

    # Desktop launcher
    if env.IS_WINDOWS or env.IS_MAC:
        if env.launcher_path().exists():
            report("ok", f"Desktop launcher: {env.launcher_path()}")
        else:
            report("warn", "No desktop launcher yet", "Run: chase-import shortcut")

    if _dashboard_running():
        report("info", f"The dashboard is running at {DASHBOARD_URL}")

    print("\nAll good!" if not failures else f"\n{failures} problem(s) to fix, marked [FAIL] above.")
    if failures:
        sys.exit(1)


def main(argv=None) -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    ap = argparse.ArgumentParser(
        prog="chase-import",
        description=HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--db", help="Postgres URL (overrides DATABASE_URL)")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the tables").set_defaults(func=cmd_init)

    lp = sub.add_parser("load", help="load export files or folders")
    lp.add_argument("paths", nargs="+", help="files and/or folders")
    lp.add_argument("--account", help="last 4 digits, if not in the file name")
    lp.add_argument("--name", help='friendly account name, e.g. "Joint checking"')
    lp.add_argument("--dry-run", action="store_true", help="parse only, no DB")
    lp.set_defaults(func=cmd_load)

    sub.add_parser("summary", help="show what's loaded").set_defaults(
        func=cmd_summary
    )

    cp = sub.add_parser("categorize", help="ask Claude to categorize leftover merchants")
    cp.add_argument("--dry-run", action="store_true", help="show answers, save nothing")
    cp.add_argument("--limit", type=int, help="only ask about the N biggest merchants")
    cp.set_defaults(func=cmd_categorize)

    sub.add_parser("dashboard", help="open the spending dashboard in your browser").set_defaults(
        func=cmd_dashboard
    )
    sub.add_parser("shortcut", help="put a Spending Dashboard launcher on the desktop").set_defaults(
        func=cmd_shortcut
    )
    sub.add_parser("backup", help="save a backup of the database into backups/").set_defaults(
        func=cmd_backup
    )
    sub.add_parser("doctor", help="check that everything is set up, and how to fix what isn't").set_defaults(
        func=cmd_doctor
    )

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
