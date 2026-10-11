"""The Import tab: add Chase downloads and categorize them, no terminal needed."""

import os
from pathlib import Path

import anthropic
import streamlit as st

from chase_import import categorize, db
from chase_import import parser as p
from chase_import.dashboard.data import load_transactions

# The project's data/ folder. This file is src/chase_import/dashboard/load.py,
# so walking up 3 parents (dashboard, chase_import, src) lands on the project root.
DATA_DIR = Path(__file__).parents[3] / "data"


def upload_and_load() -> None:
    """Pick Chase downloads, save them into data/, and load them into Postgres."""
    with st.container(key="card-upload"):
        st.subheader("1. Add Chase downloads")
        st.caption("Pick the CSV files you downloaded from chase.com. "
                   "Loading the same file twice is fine; nothing gets doubled.")

        files = st.file_uploader(
            "Chase downloads",
            type=["csv", "xlsx", "parquet"],
            accept_multiple_files=True,
        )

        # Everything below happens only on the rerun right after the click (gotcha #2)
        if not files or not st.button("Load", type="primary"):
            return

        DATA_DIR.mkdir(exist_ok=True)
        total_new = 0

        with db.connect(os.environ["DATABASE_URL"]) as conn:
            db.init_schema(conn)  # same as cmd_load: makes sure the tables exist

            for f in files:
                # --- save it into data/
                name = Path(f.name).name  # gotcha #3: drop any folder parts
                path = DATA_DIR / name
                path.write_bytes(f.getbuffer())

                try:
                    parsed = p.parse_file(path)
                except p.ParseError as e:
                    st.error(f"{path.name}: {e}")
                    continue
                if not parsed.account_last4:
                    st.error(f"{path.name}: couldn't tell which account this is. "
                             "Download it again from Chase and keep the original file "
                             "name (like Chase1234_Activity_20261009.csv).")
                    continue

                # --- load it
                new, dup = db.load_file(conn, parsed)
                total_new += new
                pending = f", {parsed.pending_skipped} pending skipped" if parsed.pending_skipped else ""
                st.success(
                    f"{name}: {new} new, {dup} already loaded "
                    f"({parsed.kind} ...{parsed.account_last4}){pending}"
                )

        load_transactions.clear()  # other tabs pick up the new rows
        st.info(f"Done. {total_new} new transactions.")


def categorize_step() -> None:
    """Ask Claude about merchants that no rule, override or saved answer covers."""
    with st.container(key="card-categorize"):
        st.subheader("2. Categorize new merchants")

        with db.connect(os.environ["DATABASE_URL"]) as conn:
            waiting = categorize.uncategorized_merchants(conn)
        if not waiting:
            st.info("Everything is categorized. Nothing to do here.")
            return

        st.caption(f"{len(waiting)} merchant(s) don't have a category yet. Only the "
                   "merchant names are sent to Claude, never amounts or account "
                   "numbers. It costs a few cents.")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            st.error("Categorizing needs an Anthropic API key: an ANTHROPIC_API_KEY=... "
                     "line in the .env file. Everything else works without it.")
            return

        if not st.button("Categorize with AI", type="primary"):
            return

        try:
            with st.spinner("Asking Claude..."), db.connect(os.environ["DATABASE_URL"]) as conn:
                found = categorize.run(conn)
        except (anthropic.APIError, ValueError) as e:
            # APIError: no credit, bad key, network down. ValueError: a reply we couldn't read.
            # Batches that finished before the error are already saved.
            st.error(f"Claude couldn't finish: {e}")
            load_transactions.clear()
            return

        load_transactions.clear()
        left = len(waiting) - len(found)
        st.success(f"Categorized {len(found)} of {len(waiting)} merchants.")
        if left:
            st.caption(f"Claude wasn't sure about {left}. Fix those on the Review tab "
                       "(Show: Uncategorized).")


def load_tab() -> None:
    """Everything on the Import tab, in the order you do it."""
    upload_and_load()
    categorize_step()
