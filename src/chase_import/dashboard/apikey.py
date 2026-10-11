"""Is a Claude API key set up, and how to set one up if not.

Its own module because two places need it: the welcome page and the Import tab.
"""

import os
from pathlib import Path

import streamlit as st
from dotenv import dotenv_values

ENV_FILE = Path(__file__).parents[3] / ".env"  # the project folder's .env
PLACEHOLDER = "sk-ant-your-key-here"  # what .env.example has, which isn't a real key


def _looks_real(key: str) -> bool:
    return key.startswith("sk-ant-") and key != PLACEHOLDER


def api_key_ready() -> bool:
    """True when a real-looking key is set.

    If it isn't loaded yet, this reads .env again, so someone who just added
    the key doesn't have to restart the dashboard.
    """
    if _looks_real(os.environ.get("ANTHROPIC_API_KEY", "")):
        return True
    key = ""
    if ENV_FILE.exists():
        key = (dotenv_values(ENV_FILE).get("ANTHROPIC_API_KEY") or "").strip()
    if _looks_real(key):
        os.environ["ANTHROPIC_API_KEY"] = key  # so Categorize can use it right away
        return True
    return False


def api_key_steps() -> None:
    """Step-by-step instructions for getting a key and putting it in .env."""
    st.markdown(
        f"""
1. Go to **<https://platform.claude.com>** and create an account.
2. Under **Billing**, add a little credit. $5 lasts a long time: categorizing a
   few hundred merchants costs well under a dollar.
3. Under **API keys**, press **Create key** and copy it. It's shown only once.
4. Open this file with **Notepad**:
"""
    )
    st.code(str(ENV_FILE), language=None)
    st.markdown(
        """
   If there's no `.env` file, copy `.env.example` in the same folder and name the
   copy `.env`. (In Notepad's *Save as*, pick **All files** so it doesn't become `.env.txt`.)
5. Find or add the line that starts with `ANTHROPIC_API_KEY=`, paste your key right
   after the `=`, and save.
6. Come back here and press **Check again**.

Keep the key private, like a password: anyone who has it can spend your credit.
"""
    )
