"""Spending dashboard. Run it with: chase-import dashboard"""

import os
from dataclasses import dataclass

import altair as alt
import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Spending", page_icon="💸", layout="wide")

# Colorblind-safe categorical palette, in a fixed order. Each group keeps its
# color no matter how the page is filtered. Light and dark are the same hues,
# adjusted for each background. Anything past the top 7 is folded into gray.
PALETTE = {
    "light": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"],
    "dark": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9"],
}
OTHER_COLOR = "#898781"
OTHER_LABEL = "All other"  # not "Other": that's a real group name in some category lists
SURFACES = {
    "light": {"page": "#f2f2ef", "card": "#ffffff",
              "border": "rgba(11,11,11,0.08)", "shadow": "rgba(0,0,0,0.06)"},
    "dark": {"page": "#0e1117", "card": "#1a1c23",
             "border": "rgba(255,255,255,0.08)", "shadow": "rgba(0,0,0,0.45)"},
}
TOP_GROUPS = len(PALETTE["light"])


# =================================================================== data


@st.cache_data(ttl=60)
def load_transactions() -> pd.DataFrame:
    """Every transaction with its final category, straight from the view."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT date, account, merchant, amount, category, subcategory,
                   is_spending, tax_relevant, category_source
            FROM transactions_categorized
            """
        )
        columns = [c.name for c in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=columns)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    return df


# =================================================================== look & feel


def theme_mode() -> str:
    """'dark' or 'light', following Streamlit's current theme."""
    theme = getattr(getattr(st, "context", None), "theme", None)
    return "dark" if getattr(theme, "type", None) == "dark" else "light"


def apply_card_styles(mode: str) -> None:
    """Gray page + white floating cards (dark: near-black page, lifted cards)."""
    s = SURFACES[mode]
    st.markdown(
        f"""
        <style>
        .stApp {{ background: {s['page']}; }}
        [data-testid="stHeader"] {{ background: transparent; }}
        [class*="st-key-card"] {{
            background: {s['card']};
            border: 1px solid {s['border']};
            border-radius: 12px;
            box-shadow: 0 1px 2px {s['shadow']}, 0 6px 16px {s['shadow']};
            padding: 1rem 1.25rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


@dataclass
class ColorKey:
    """Which labels get their own color, and which color each one gets."""

    named: list[str]  # the top labels, biggest spending first
    colors: list[str]  # one color per named label, plus gray for the rest

    @property
    def order(self) -> list[str]:
        return self.named + [OTHER_LABEL]

    def label(self, values: pd.Series) -> pd.Series:
        """Keep the named labels; fold everything else into OTHER_LABEL."""
        return values.where(values.isin(self.named), OTHER_LABEL)


def build_color_key(labels: pd.Series, amounts: pd.Series, mode: str) -> ColorKey:
    """Rank labels by total spending and give the top ones a fixed color.

    Call it with ALL-TIME data, not filtered data, so changing a filter never
    repaints a group.
    """
    ranked = amounts.groupby(labels).sum().sort_values().index  # most negative = most spent
    named = list(ranked[:TOP_GROUPS])
    return ColorKey(named=named, colors=PALETTE[mode][: len(named)] + [OTHER_COLOR])


def money(x: float) -> str:
    return f"-${-x:,.0f}" if x < 0 else f"${x:,.0f}"


# =================================================================== page pieces


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


def top_merchants_card(spending: pd.DataFrame, limit: int = 15) -> None:
    """The merchants you spent the most at."""
    with st.container(key="card-merchants"):
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


# =================================================================== the page

mode = theme_mode()
apply_card_styles(mode)

df = load_transactions()
if df.empty:
    st.info("No transactions yet. Run `chase-import load data` first.")
    st.stop()

all_spending = df[df["is_spending"]]
group_colors = build_color_key(all_spending["category"], all_spending["amount"], mode)

st.title("💸 Spending")
view = filter_controls(df)
spending = view[view["is_spending"]]

(overview,) = st.tabs(["Overview"])

with overview:
    headline_tiles(view, spending)
    monthly_spending_card(spending, "category", group_colors, mode)
    top_merchants_card(spending)
