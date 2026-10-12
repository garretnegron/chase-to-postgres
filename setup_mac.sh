#!/bin/bash
# One-time setup on a Mac. In Terminal, from this folder, run:
#
#     bash setup_mac.sh
#
# Before running it, install Python (python.org) and Postgres.app (postgresapp.com),
# and open Postgres.app once so the elephant is in the menu bar.
#
# It's safe to run again: each step skips what's already done.

set -euo pipefail
cd "$(dirname "$0")"  # always work in the project folder, wherever it's run from

DB_NAME="finances"
DB_URL="${DATABASE_URL:-postgresql://localhost:5432/$DB_NAME}"

step() { printf '\n==> %s\n' "$1"; }
ok()   { printf '    %s\n' "$1"; }
fail() { printf '\n[FAIL] %s\n\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------- 1. Python
step "Looking for Python 3.10 or newer"
PY=""
# Versioned names first: plain python3 can be Apple's old 3.9, or a stub that
# pops up an "install developer tools" dialog.
for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        PY="$(command -v "$candidate")"
        break
    fi
done
[ -n "$PY" ] || fail "No Python 3.10 or newer found. Install it from https://www.python.org/downloads/macos/ and run this again."
ok "Found $("$PY" --version) at $PY"

# ---------------------------------------------------------------- 2. PostgreSQL
step "Looking for PostgreSQL"
if ! command -v psql >/dev/null 2>&1; then
    # Postgres.app and Homebrew don't always put their tools on the PATH
    for dir in /Applications/Postgres.app/Contents/Versions/latest/bin \
               /opt/homebrew/opt/postgresql@*/bin /usr/local/opt/postgresql@*/bin; do
        if [ -x "$dir/psql" ]; then
            export PATH="$dir:$PATH"
            break
        fi
    done
fi
command -v psql >/dev/null 2>&1 || fail "PostgreSQL isn't installed. Install Postgres.app from https://postgresapp.com, open it, click Initialize, then run this again."
ok "Found $(psql --version)"

if ! pg_isready -h localhost -p 5432 -q; then
    fail "PostgreSQL isn't running. Open Postgres.app (look for the elephant in the menu bar) and click Start or Initialize, then run this again."
fi
ok "PostgreSQL is running"

# ---------------------------------------------------------------- 3. the database
step "Creating the '$DB_NAME' database"
if psql -h localhost -d "$DB_NAME" -c 'SELECT 1' >/dev/null 2>&1; then
    ok "Already there"
else
    createdb -h localhost "$DB_NAME" || fail "Couldn't create the database. Is Postgres.app running?"
    ok "Created"
fi

# ---------------------------------------------------------------- 4. the app
step "Installing the app (this takes a minute or two the first time)"
if [ ! -x .venv/bin/python ]; then
    "$PY" -m venv .venv
fi
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -e ".[dashboard]"
ok "Installed"

# ---------------------------------------------------------------- 5. settings
step "Writing the settings file (.env)"
if [ -f .env ]; then
    ok ".env already exists, so it was left as it is"
else
    {
        echo "# Settings for chase-to-postgres. Made by setup_mac.sh; never committed to git."
        echo "DATABASE_URL=$DB_URL"
        echo "# The Claude API key gets added here when you paste it into the dashboard."
    } > .env
    ok "Created .env"
fi

# ---------------------------------------------------------------- 6. tables + launcher
step "Creating the tables"
.venv/bin/chase-import init

step "Putting Spending Dashboard on the Desktop"
.venv/bin/chase-import shortcut

# ---------------------------------------------------------------- 7. check
step "Checking everything"
.venv/bin/chase-import doctor

printf '\nAll set! Double-click "Spending Dashboard" on your Desktop to open it.\n'
printf 'The welcome page walks you through the rest.\n\n'
