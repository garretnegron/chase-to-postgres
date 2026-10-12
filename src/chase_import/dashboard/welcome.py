"""First-run pages: the welcome checklist, and help when the database can't be reached."""

import pandas as pd
import streamlit as st

from chase_import.env import ENV_FILE, IS_MAC, PROJECT_DIR
from chase_import.dashboard.apikey import api_key_form, api_key_ready
from chase_import.dashboard.load import upload_and_load
from chase_import.dashboard.settings import file_card
from chase_import.dashboard.theme import signature

STARTER_LISTS = PROJECT_DIR / "starter_lists"


def needs_welcome(df: pd.DataFrame, cats: pd.DataFrame) -> bool:
    """Show the welcome page until there's a category list and some transactions."""
    if st.session_state.get("skip_welcome"):
        return False
    only_uncategorized = len(cats) <= 1
    return only_uncategorized or df.empty


def step_title(number: int, title: str, done: bool, optional: bool = False) -> None:
    mark = "✅" if done else "⬜"
    extra = " (optional)" if optional and not done else ""
    st.subheader(f"{mark} {number}. {title}{extra}")


def good_to_know() -> None:
    with st.container(key="card-welcome-facts"):
        st.subheader("Good to know")
        st.markdown(
            """
- 🔒 **Your data stays on this computer.** Bank files and the database never leave it.
  Categorizing sends only merchant names (like `PUBLIX #854`) to Claude, never
  amounts or account numbers.
- 📥 **Downloading from Chase:** on chase.com, open an account, click the
  **download** icon above the transactions, pick **CSV** and a date range.
  Overlapping an earlier download is fine: nothing gets counted twice.
- 🏷️ **Don't rename the files.** The `Chase1234` part of the name tells the app
  which account it is.
- ⏳ **Pending transactions are skipped** until they post. Download again in a few
  days and they'll come in.
- 🔁 **Your routine:** **Import** tab → **Load** → **Categorize with AI** → glance at **Review**.
- ✋ **Mistakes are easy to fix:** change any transaction on **Review**; add or
  rename categories on **Settings**.
"""
        )


def welcome_page(df: pd.DataFrame, cats: pd.DataFrame) -> None:
    """The first-run checklist. Each step shows what's done and how to do the rest."""
    has_categories = len(cats) > 1
    has_key = api_key_ready()
    has_data = not df.empty

    st.title("👋 Welcome")
    st.write("A few one-time steps and you're ready to go. You can come back to any of "
             "them later.")
    done = sum([has_categories, has_key, has_data])
    st.progress(done / 3, text=f"{done} of 3 done")

    # ---- 1. categories
    step_title(1, "Your category list", has_categories)
    if has_categories:
        st.caption(f"{len(cats)} subcategories ready. Change them any time on the Settings tab.")
    else:
        st.write("Upload a spreadsheet of your groups and subcategories. Ready-made "
                 "lists are in this folder, or download the blank template below and fill it in:")
        st.code(str(STARTER_LISTS), language=None)
        file_card(cats, show_export=False)

    # ---- 2. API key
    step_title(2, "Your Claude API key", has_key, optional=True)
    if has_key:
        st.caption("Found. Categorize with AI is ready to use.")
    else:
        with st.container(key="card-welcome-key"):
            st.write("Only needed for **Categorize with AI**, which sorts new merchants "
                     "for you. Everything else works without it.")
            api_key_form("welcome-key")

    # ---- 3. data
    step_title(3, "Your Chase downloads", has_data)
    if has_data:
        st.caption(f"{len(df):,} transactions loaded.")
    else:
        upload_and_load()  # reruns the page after loading: step 3 turns green

    # ---- finish
    if has_categories and has_data:
        st.success("You're all set!")
        st.button("Open my dashboard", type="primary", key="welcome-open")
    else:
        col_check, col_skip = st.columns(2)
        col_check.button("Check again", key="welcome-check-all")
        if has_data and col_skip.button("Skip for now", key="welcome-skip"):
            st.session_state["skip_welcome"] = True
            st.rerun()

    good_to_know()
    signature()


WINDOWS_DB_FIXES = f"""
1. **Is PostgreSQL running?** Press the Windows key, type **Services**, open it, find
   **postgresql-x64-…**, and make sure its status is **Running** (right-click → **Start**).
2. **Is the password right?** Open `{ENV_FILE}` in Notepad. The `DATABASE_URL=` line
   has the Postgres password in it, between `postgres:` and `@localhost`.
3. **Does the database exist?** It's called `finances` in the setup steps.
"""

MAC_DB_FIXES = f"""
1. **Is PostgreSQL running?** With Postgres.app, look for the elephant 🐘 in the menu bar
   at the top of the screen and click it. If it offers **Start**, click it. No elephant?
   Open **Postgres.app** from your Applications folder.
2. **Are the connection details right?** They're on the `DATABASE_URL=` line in
   `{ENV_FILE}`. With Postgres.app it's usually just
   `postgresql://localhost:5432/finances` (no password). The file is hidden in Finder:
   press **Cmd + Shift + .** to show it, then open it with TextEdit.
3. **Does the database exist?** It's called `finances` in the setup steps.
"""


def database_problem(error: Exception) -> None:
    """Shown instead of everything else when Postgres can't be reached."""
    st.title("😕 Can't reach your database")
    with st.container(key="card-db-problem"):
        st.markdown("The dashboard couldn't connect to PostgreSQL. The usual fixes:")
        st.markdown(MAC_DB_FIXES if IS_MAC else WINDOWS_DB_FIXES)
        st.markdown("Then refresh this page. For a full check of the setup, run "
                    "`chase-import doctor` in the project folder.")
        with st.expander("Technical details"):
            st.code(str(error), language=None)
    signature()
