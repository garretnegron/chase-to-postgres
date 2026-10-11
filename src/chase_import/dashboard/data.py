"""Everything the dashboard reads from and writes to Postgres."""

import os

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


@st.cache_data(ttl=60)
def load_transactions() -> pd.DataFrame:
    """Every transaction with its final category, straight from the view."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT row_hash, date, account, merchant, amount, category, subcategory,
                   is_spending, tax_relevant, category_source
            FROM transactions_categorized
            """
        )
        columns = [c.name for c in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=columns)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    return df


@st.cache_data(ttl=60)
def load_subcategories() -> list[str]:
    """Every subcategory you can pick, grouped by category."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute("SELECT subcategory FROM categories ORDER BY category, subcategory")
        return [row[0] for row in cur.fetchall()]


def save_overrides(changes: dict[str, str]) -> None:
    """Save manual fixes: {row_hash: subcategory}.

    Fixing the same transaction again replaces the earlier fix (DO UPDATE),
    and keeps any note you wrote on it by hand.
    """
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO category_overrides (row_hash, subcategory)
            VALUES (%s, %s)
            ON CONFLICT (row_hash) DO UPDATE
                SET subcategory = EXCLUDED.subcategory, created_at = now()
            """,
            list(changes.items()),
        )
    # leaving the `with` block commits
    load_transactions.clear()  # so every tab shows the fix on the next run
