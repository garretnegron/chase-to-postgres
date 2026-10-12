"""The Claude API key: is one set up, and a box to paste one in if not.

The checking and saving live in chase_import.env (so the command line can use
them too); this is just the dashboard's form.
"""

import streamlit as st

from chase_import.env import ENV_FILE, api_key_ready, looks_like_api_key, save_api_key
from chase_import.dashboard.notify import rerun_with

__all__ = ["api_key_ready", "api_key_form"]


def api_key_form(key: str) -> None:
    """How to get a key, and a box to paste it into. Saving writes it to .env.

    `key` keeps the widgets apart when the form appears in more than one place.
    """
    st.markdown(
        """
1. Go to **<https://platform.claude.com>** and create an account.
2. Under **Billing**, add a little credit. $5 lasts a long time: categorizing a
   few hundred merchants costs well under a dollar.
3. Under **API keys**, press **Create key** and copy it. It's shown only once.
4. Paste it below and press **Save key**.
"""
    )
    pasted = st.text_input("Your API key", type="password", placeholder="sk-ant-...",
                           key=f"{key}-input").strip()
    if not st.button("Save key", key=f"{key}-save", disabled=not pasted):
        st.caption(f"It's saved in {ENV_FILE}, on this computer only. Keep it private, like "
                   "a password: anyone who has it can spend your credit.")
        return
    if not looks_like_api_key(pasted):
        st.error("That doesn't look like a Claude API key. They start with `sk-ant-`; "
                 "copy it again from platform.claude.com.")
        return
    save_api_key(pasted)
    st.session_state.pop(f"{key}-input", None)  # don't leave the key sitting in the box
    rerun_with("API key saved. Categorize with AI is ready.")
