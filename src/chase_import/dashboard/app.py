"""Spending dashboard. Run it with: chase-import dashboard

This is the file Streamlit runs, top to bottom, on every click. It sets up the
page and the filters, then hands each tab to its own module.

Imports are absolute (chase_import.dashboard.x, not .x) because Streamlit runs
this file as a script, not as part of the package.
"""

import pandas as pd
import psycopg
import streamlit as st

from chase_import.dashboard.categories import categories_tab
from chase_import.dashboard.data import (
    ensure_schema, load_category_table, load_subcategories, load_transactions,
)
from chase_import.dashboard.load import load_tab, upload_and_load
from chase_import.dashboard.notify import show_toasts
from chase_import.dashboard.overview import overview_tab
from chase_import.dashboard.review import review_tab
from chase_import.dashboard.settings import settings_tab
from chase_import.dashboard.theme import apply_card_styles, build_color_key, signature, theme_mode
from chase_import.dashboard.welcome import database_problem, needs_welcome, welcome_page

st.set_page_config(page_title="Spending", page_icon="💸", layout="wide")


def filter_controls(df: pd.DataFrame) -> pd.DataFrame:
    """Date range + account pickers. Returns the transactions that match."""
    first_day, last_day = df["date"].min().date(), df["date"].max().date()
    col_dates, col_accounts = st.columns([2, 3])
    picked = col_dates.date_input(
        "Dates", value=(first_day, last_day), min_value=first_day, max_value=last_day
    )
    all_accounts = sorted(df["account"].unique())
    chosen = col_accounts.multiselect("Accounts", all_accounts, default=all_accounts)

    if len(picked) != 2:  # still picking the end date
        st.stop()
    start, end = picked
    return df[
        (df["date"].dt.date >= start)
        & (df["date"].dt.date <= end)
        & df["account"].isin(chosen)
    ]


# =================================================================== the page

mode = theme_mode()
apply_card_styles(mode)
show_toasts()  # "Saved!" pop-ups from just before a rerun

try:
    ensure_schema()  # creates the tables on a brand-new database
except (psycopg.OperationalError, KeyError) as error:  # can't connect, or no DATABASE_URL
    database_problem(error)
    st.stop()

df = load_transactions()
cats = load_category_table()
if needs_welcome(df, cats):
    welcome_page(df, cats)
    st.stop()
if df.empty:
    # Skipped the welcome page with nothing loaded: nothing to chart yet.
    st.info("No transactions yet. Add your Chase downloads to get started.")
    upload_and_load()
    st.stop()

st.title("💸 Spending")

all_spending = df[df["is_spending"]]
group_colors = build_color_key(all_spending["category"], all_spending["amount"], mode)

view = filter_controls(df)
spending = view[view["is_spending"]]

importer, overview, categories, review, settings = st.tabs(
    ["Import", "Overview", "Categories", "Review", "Settings"]
)

with importer:  # not `import`: that word is reserved by Python
    load_tab()

with overview:
    overview_tab(view, spending, group_colors, mode)

with categories:
    categories_tab(spending, all_spending, mode)

with review:
    review_tab(view, load_subcategories())

with settings:
    settings_tab()

signature()
