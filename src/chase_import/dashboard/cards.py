"""Cards that more than one tab uses."""

import altair as alt
import pandas as pd
import streamlit as st

from chase_import.dashboard.theme import SURFACES, ColorKey


def monthly_spending_card(
    spending: pd.DataFrame,
    by: str,
    colors: ColorKey,
    mode: str,
    title: str = "Spending by month",
    key: str = "card-monthly",
) -> None:
    """Stacked monthly spending, one color per label in the `by` column.

    by="category" stacks groups; by="subcategory" stacks subcategories, which
    is what the Categories tab will use.
    """
    with st.container(key=key):
        st.subheader(title)
        monthly = (
            spending.assign(
                month=spending["date"].dt.to_period("M").dt.to_timestamp(),
                label=colors.label(spending[by]),
            )
            .groupby(["month", "label"], as_index=False)["amount"]
            .sum()
        )
        monthly["spent"] = -monthly["amount"]
        monthly["stack_order"] = monthly["label"].map(colors.order.index)

        chart = (
            alt.Chart(monthly)
            .mark_bar(stroke=SURFACES[mode]["card"], strokeWidth=1)
            .encode(
                x=alt.X("yearmonth(month):O", title=None, axis=alt.Axis(format="%b", labelAngle=0)),
                y=alt.Y("sum(spent):Q", title=None, axis=alt.Axis(format="$,.0f")),
                color=alt.Color(
                    "label:N",
                    scale=alt.Scale(domain=colors.order, range=colors.colors),
                    legend=alt.Legend(title=None, orient="bottom"),
                ),
                order=alt.Order("stack_order:Q"),
                tooltip=[
                    alt.Tooltip("yearmonth(month):T", title="Month", format="%B %Y"),
                    alt.Tooltip("label:N", title=by.capitalize()),
                    alt.Tooltip("spent:Q", title="Spent", format="$,.2f"),
                ],
            )
            .properties(height=360, width="container", background="transparent")
        )
        st.altair_chart(chart)

        with st.expander("Show as table"):
            present = set(monthly["label"])
            table = monthly.pivot_table(
                index="month", columns="label", values="spent", aggfunc="sum", fill_value=0
            ).reindex(columns=[label for label in colors.order if label in present])
            table.index = table.index.strftime("%b %Y")
            st.dataframe(table.style.format("${:,.2f}"))


def top_merchants_card(spending: pd.DataFrame, limit: int = 15, key: str = "card-merchants") -> None:
    """The merchants you spent the most at."""
    with st.container(key=key):
        st.subheader("Top merchants")
        top = (
            spending.groupby("merchant")
            .agg(visits=("amount", "size"), spent=("amount", "sum"), group=("category", "first"))
            .assign(spent=lambda d: -d["spent"])
            .sort_values("spent", ascending=False)
            .head(limit)
            .reset_index()
        )
        st.dataframe(
            top,
            hide_index=True,
            column_config={
                "merchant": "Merchant",
                "group": "Group",
                "visits": st.column_config.NumberColumn("Visits"),
                "spent": st.column_config.NumberColumn("Spent", format="$%.2f"),
            },
        )
