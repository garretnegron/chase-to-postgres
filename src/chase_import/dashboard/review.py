"""The Review tab: fix categories by hand. Fixes go to category_overrides."""

import pandas as pd
import streamlit as st

from chase_import.dashboard.data import save_overrides

# What the "Show" picker offers, and the category_source each one keeps.
# None means uncategorized; "all" means don't filter.
SHOW = {
    "Decided by AI": "ai",
    "Uncategorized": None,
    "Decided by a rule": "rule",
    "Fixed by hand": "manual",
    "Everything": "all",
}
COLUMNS = ["date", "account", "merchant", "amount", "subcategory", "category", "category_source"]


def pick_rows(view: pd.DataFrame) -> pd.DataFrame:
    """The Show + search pickers. Returns the transactions to review."""
    col_show, col_search = st.columns([2, 3])
    source = SHOW[col_show.selectbox("Show", list(SHOW))]
    search = col_search.text_input("Merchant contains")

    rows = view
    if source is None:
        rows = rows[rows["category_source"].isna()]
    elif source != "all":
        rows = rows[rows["category_source"] == source]
    if search:
        rows = rows[rows["merchant"].str.contains(search, case=False, regex=False)]
    return rows


def review_tab(view: pd.DataFrame, subcategories: list[str]) -> None:
    """Pick rows, change their subcategory in the table, then save."""
    saved = st.session_state.pop("review_saved", None)  # set just before the rerun below
    if saved:
        st.toast(f"Saved {saved} fix(es).")

    rows = pick_rows(view)
    if rows.empty:
        st.info("Nothing to review here.")
        return

    # row_hash becomes the (hidden) index: it's how each edited row finds its transaction
    table = rows.sort_values("date", ascending=False).set_index("row_hash")[COLUMNS]

    with st.container(key="card-review"):
        st.subheader(f"{len(table):,} transactions")
        st.caption("Change a subcategory, then press Save. Changing the filters "
                   "above throws away edits you haven't saved.")
        edited = st.data_editor(
            table,
            hide_index=True,
            disabled=[c for c in COLUMNS if c != "subcategory"],  # only subcategory is editable
            column_config={
                "date": st.column_config.DateColumn("Date", format="MMM D, YYYY"),
                "account": "Account",
                "merchant": "Merchant",
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                "subcategory": st.column_config.SelectboxColumn(
                    "Subcategory", options=subcategories, required=True
                ),
                "category": "Group",
                "category_source": "Decided by",
            },
            # A new key = a fresh editor. It changes whenever the rows do,
            # so leftover edits can never land on the wrong transaction.
            key=f"review-{hash(tuple(table.index))}",
        )

        changed = edited["subcategory"] != table["subcategory"]
        count = int(changed.sum())
        if st.button(f"Save {count} change(s)", type="primary", disabled=count == 0):
            save_overrides(edited.loc[changed, "subcategory"].to_dict())
            st.session_state["review_saved"] = count
            st.rerun()
