"""Everything the dashboard reads from and writes to Postgres."""

import os

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

from chase_import import db

load_dotenv()


@st.cache_resource
def ensure_schema() -> None:
    """Create or update the tables, once per dashboard start.

    cache_resource runs this the first time only. If it fails (say, Postgres
    isn't running), nothing is cached, so the next refresh tries again.
    """
    with db.connect(os.environ["DATABASE_URL"]) as conn:
        db.init_schema(conn)


@st.cache_data(ttl=60)
def load_transactions() -> pd.DataFrame:
    """Every transaction with its final category, straight from the view."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        try:
            cur.execute(
                """
                SELECT row_hash, date, account, merchant, amount, category, subcategory,
                       is_spending, tax_relevant, category_source
                FROM transactions_categorized
                """
            )
        except psycopg.errors.UndefinedTable:
            return pd.DataFrame()  # brand-new database: the tables don't exist yet
        columns = [c.name for c in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=columns)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)

    # Money coming IN that nobody has categorized yet (a paycheck, a card payment,
    # a refund) isn't spending. Counted as spending it would subtract from your
    # totals and push months below zero. Treat it as money in until it's categorized.
    uncategorized_in = df["category_source"].isna() & (df["amount"] > 0)
    df["is_spending"] = df["is_spending"] & ~uncategorized_in
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


# ---------------------------------------------------------------- categories


@st.cache_data(ttl=60)
def load_category_table() -> pd.DataFrame:
    """The categories table: subcategory, group, and the two flags."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT subcategory, category, is_spending, tax_relevant
            FROM categories
            ORDER BY category, subcategory
            """
        )
        columns = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=columns)


def clear_caches() -> None:
    """After changing categories, every cached read is out of date."""
    load_transactions.clear()
    load_subcategories.clear()
    load_category_table.clear()


def add_category(subcategory: str, group: str, is_spending: bool, tax_relevant: bool) -> None:
    """Add one subcategory. A new group name creates the group."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(
            "INSERT INTO categories (subcategory, category, is_spending, tax_relevant) "
            "VALUES (%s, %s, %s, %s)",
            (subcategory, group, is_spending, tax_relevant),
        )
    clear_caches()


def update_categories(rows: list[tuple[str, str, str, bool, bool]]) -> None:
    """Save edits: each row is (old name, new name, group, is_spending, tax_relevant).

    Renaming works because of ON UPDATE CASCADE: rules, overrides and AI
    answers follow the new name automatically.
    """
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.executemany(
            """
            UPDATE categories
            SET subcategory = %s, category = %s, is_spending = %s, tax_relevant = %s
            WHERE subcategory = %s
            """,
            [(new, group, spending, tax, old) for old, new, group, spending, tax in rows],
        )
    clear_caches()


def apply_category_list(rows: list[tuple[str, str, bool, bool]]) -> None:
    """Add or update many subcategories at once, from an uploaded list.

    Each row is (subcategory, group, is_spending, tax_relevant). New names are
    added; existing ones get the group and flags from the file. Nothing is
    deleted. One transaction: the whole file goes in, or none of it does.
    """
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO categories (subcategory, category, is_spending, tax_relevant)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (subcategory) DO UPDATE
                SET category     = EXCLUDED.category,
                    is_spending  = EXCLUDED.is_spending,
                    tax_relevant = EXCLUDED.tax_relevant
            """,
            rows,
        )
    clear_caches()


def category_usage(subcategory: str) -> dict[str, int]:
    """How much points at one subcategory, so you know what removing it moves."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                (SELECT count(*) FROM transactions_categorized WHERE subcategory = %(s)s),
                (SELECT count(*) FROM category_rules           WHERE subcategory = %(s)s),
                (SELECT count(*) FROM category_overrides       WHERE subcategory = %(s)s),
                (SELECT count(*) FROM merchant_categories      WHERE subcategory = %(s)s)
            """,
            {"s": subcategory},
        )
        transactions, rules, fixes, ai = cur.fetchone()
    return {"transactions": transactions, "rules": rules, "fixes": fixes, "ai": ai}


def remove_category(subcategory: str, replacement: str) -> None:
    """Point everything at `replacement` instead, then delete `subcategory`.

    Moving to "Uncategorized" deletes the rules, fixes and AI answers instead,
    so those transactions are truly uncategorized again: they show up under
    Review > Uncategorized, and the next AI run can take a fresh look.

    All in one transaction: if any step fails, nothing changes.
    """
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.transaction():
        # Table names can't be %s parameters, so they go in with an f-string.
        # That's safe here only because they come from this fixed list, never from a user.
        for table in ("category_rules", "category_overrides", "merchant_categories"):
            if replacement == "Uncategorized":
                conn.execute(f"DELETE FROM {table} WHERE subcategory = %s", (subcategory,))
            else:
                conn.execute(
                    f"UPDATE {table} SET subcategory = %s WHERE subcategory = %s",
                    (replacement, subcategory),
                )
        conn.execute("DELETE FROM categories WHERE subcategory = %s", (subcategory,))
    clear_caches()
