"""The Overview tab: headline numbers, spending by group, top merchants."""

import pandas as pd
import streamlit as st

from chase_import.dashboard.cards import monthly_spending_card, top_merchants_card
from chase_import.dashboard.theme import ColorKey, money


def tile(column, key: str, label: str, value: str) -> None:
    """One headline number in its own card."""
    with column.container(key=f"card-{key}"):
        st.metric(label, value)


def headline_tiles(view: pd.DataFrame, spending: pd.DataFrame) -> None:
    """Four headline numbers across the top."""
    spent = -spending["amount"].sum()
    money_in = view.loc[~view["is_spending"] & (view["amount"] > 0), "amount"].sum()
    months = max(spending["date"].dt.to_period("M").nunique(), 1)

    t1, t2, t3, t4 = st.columns(4)
    tile(t1, "spent", "Spent", money(spent))
    tile(t2, "avg", "Avg per month", money(spent / months))
    tile(t3, "in", "Money in", money(money_in))
    tile(t4, "net", "Money in minus spent", money(money_in - spent))


def overview_tab(
    view: pd.DataFrame, spending: pd.DataFrame, group_colors: ColorKey, mode: str
) -> None:
    """Everything on the Overview tab, top to bottom."""
    headline_tiles(view, spending)
    monthly_spending_card(spending, "category", group_colors, mode)
    top_merchants_card(spending)
