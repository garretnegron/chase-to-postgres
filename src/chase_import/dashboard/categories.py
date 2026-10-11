"""The Categories tab: drill into one group."""

import pandas as pd
import streamlit as st

from chase_import.dashboard.cards import monthly_spending_card, top_merchants_card
from chase_import.dashboard.theme import build_color_key


def categories_tab(spending: pd.DataFrame, all_spending: pd.DataFrame, mode: str) -> None:
    """Drill into one group: its subcategories month by month, and its merchants."""
    groups = all_spending.groupby("category")["amount"].sum().sort_values().index  # the group names, biggest spending first
    group = st.selectbox("Group", groups)

    in_group = spending[spending["category"] == group]
    if in_group.empty:
        st.info(f"No {group} spending in the selected dates.")
        return
    all_in_group = all_spending[all_spending["category"] == group]

    # Colors for this group's subcategories, from ALL-TIME data so filters don't repaint them
    sub_colors = build_color_key(all_in_group["subcategory"], all_in_group["amount"], mode)

    monthly_spending_card(in_group, "subcategory", sub_colors, mode,
                          title=f"{group} by month", key="card-group-monthly")
    top_merchants_card(in_group, key="card-group-merchants")
