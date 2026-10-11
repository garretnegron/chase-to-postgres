"""Command line: chase-import init | load | summary | categorize"""

from __future__ import annotations

import argparse
import os
import sys

from . import parser as p

HELP = """\
Load Chase CSV / Excel / Parquet exports into Postgres.

  chase-import init                       create the tables (safe to re-run)
  chase-import load downloads/            load every export in a folder
  chase-import load file.csv --account 1234 --name "Dad checking"
  chase-import load downloads/ --dry-run  check files without touching the DB
  chase-import summary                    what's in the database
  chase-import categorize --dry-run       ask Claude about uncategorized merchants, save nothing
  chase-import categorize                 ask Claude and save the answers

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
    lp.add_argument("--name", help='friendly account name, e.g. "Dad checking"')
    lp.add_argument("--dry-run", action="store_true", help="parse only, no DB")
    lp.set_defaults(func=cmd_load)

    sub.add_parser("summary", help="show what's loaded").set_defaults(
        func=cmd_summary
    )

    cp = sub.add_parser("categorize", help="ask Claude to categorize leftover merchants")
    cp.add_argument("--dry-run", action="store_true", help="show answers, save nothing")
    cp.add_argument("--limit", type=int, help="only ask about the N biggest merchants")
    cp.set_defaults(func=cmd_categorize)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
