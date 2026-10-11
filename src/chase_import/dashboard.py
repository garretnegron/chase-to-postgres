"""Spending dashboard. Run it with: chase-import dashboard"""

import os

import altair as alt
import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Spending", page_icon="💸", layout="wide")

# Colorblind-safe categorical palette, in a fixed order. Each group keeps its
# color no matter how the page is filtered. Light and dark are the same hues,
# adjusted for each background. Groups past the top 7 are shown as gray "Other".
PALETTE = {
    "light": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"],
    "dark": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9"],
}
OTHER_COLOR = "#898781"
#BACKGROUND = {"light": "#ffffff", "dark": "#0e1117"}  # Streamlit's page colors
SURFACES = {
    "light": {"page": "#f2f2ef", "card": "#ffffff",
              "border": "rgba(11,11,11,0.08)", "shadow": "rgba(0,0,0,0.06)"},
    "dark": {"page": "#0e1117", "card": "#1a1c23",
             "border": "rgba(255,255,255,0.08)", "shadow": "rgba(0,0,0,0.45)"},
}
TOP_GROUPS = len(PALETTE["light"])


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


def theme_mode() -> str:
    """'dark' or 'light', following Streamlit's current theme."""
    theme = getattr(getattr(st, "context", None), "theme", None)
    return "dark" if getattr(theme, "type", None) == "dark" else "light"


def money(x: float) -> str:
    return f"-${-x:,.0f}" if x < 0 else f"${x:,.0f}"

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


def tile(column, key: str, label: str, value: str) -> None:
    """One headline number in its own card."""
    with column.container(key=f"card-{key}"):
        st.metric(label, value)


df = load_transactions()

if df.empty:
    st.info("No transactions yet. Run `chase-import load data` first.")
    st.stop()

# ----------------------------------------------------------- group colors
# Rank groups by ALL-TIME spending, once, so filters never repaint a group.
all_spending = df[df["is_spending"]]
ranked = all_spending.groupby("category")["amount"].sum().sort_values().index
named_groups = list(ranked[:TOP_GROUPS])  # most negative = most spent
group_order = named_groups + ["Other"]
mode = theme_mode()
apply_card_styles(mode)
group_colors = PALETTE[mode][: len(named_groups)] + [OTHER_COLOR]


def display_group(category: str) -> str:
    return category if category in named_groups else "Other"


# ----------------------------------------------------------- header + filters
st.title("💸 Spending")

first_day, last_day = df["date"].min().date(), df["date"].max().date()
col_dates, col_accounts = st.columns([2, 3])
picked = col_dates.date_input(
    "Dates", value=(first_day, last_day), min_value=first_day, max_value=last_day
)
all_accounts = sorted(df["account"].unique())
chosen_accounts = col_accounts.multiselect("Accounts", all_accounts, default=all_accounts)

if len(picked) != 2:  # still picking the end date
    st.stop()
start, end = picked

view = df[
    (df["date"].dt.date >= start)
    & (df["date"].dt.date <= end)
    & df["account"].isin(chosen_accounts)
]
spending = view[view["is_spending"]]

(overview,) = st.tabs(["Overview"])

# ----------------------------------------------------------- overview tab
with overview:
    spent = -spending["amount"].sum()
    money_in = view.loc[~view["is_spending"] & (view["amount"] > 0), "amount"].sum()
    months = max(spending["date"].dt.to_period("M").nunique(), 1)

    t1, t2, t3, t4 = st.columns(4)
    tile(t1, "spent", "Spent", money(spent))
    tile(t2, "avg", "Avg per month", money(spent / months))
    tile(t3, "in", "Money in", money(money_in))
    tile(t4, "net", "Money in minus spent", money(money_in - spent))

    with st.container(key="card-monthly"):
        st.subheader("Spending by month")
        monthly = (
            spending.assign(
                month=spending["date"].dt.to_period("M").dt.to_timestamp(),
                group=spending["category"].map(display_group),
            )
            .groupby(["month", "group"], as_index=False)["amount"]
            .sum()
        )
        monthly["spent"] = -monthly["amount"]
        monthly["stack_order"] = monthly["group"].map(group_order.index)

        chart = (
            alt.Chart(monthly)
            .mark_bar(stroke=SURFACES[mode]["card"], strokeWidth=1)
            .encode(
                x=alt.X("yearmonth(month):O", title=None, axis=alt.Axis(format="%b", labelAngle=0)),
                y=alt.Y("sum(spent):Q", title=None, axis=alt.Axis(format="$,.0f")),
                color=alt.Color(
                    "group:N",
                    scale=alt.Scale(domain=group_order, range=group_colors),
                    legend=alt.Legend(title=None, orient="bottom"),
                ),
                order=alt.Order("stack_order:Q"),
                tooltip=[
                    alt.Tooltip("yearmonth(month):T", title="Month", format="%B %Y"),
                    alt.Tooltip("group:N", title="Group"),
                    alt.Tooltip("spent:Q", title="Spent", format="$,.2f"),
                ],
            )
            .properties(height=360, width="container", background="transparent")
        )
        st.altair_chart(chart)

    with st.expander("Show as table"):
        table = monthly.pivot_table(
            index="month", columns="group", values="spent", aggfunc="sum", fill_value=0
        ).reindex(columns=[g for g in group_order if g in monthly["group"].unique()])
        table.index = table.index.strftime("%b %Y")
        st.dataframe(table.style.format("${:,.2f}"))

    with st.container(key="card-merchants"):
        st.subheader("Top merchants")
        top = (
            spending.groupby("merchant")
            .agg(visits=("amount", "size"), spent=("amount", "sum"), group=("category", "first"))
            .assign(spent=lambda d: -d["spent"])
            .sort_values("spent", ascending=False)
            .head(15)
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