"""Messages that survive a rerun.

After anything that changes data (loading, categorizing, saving), the page has
to start over so every tab redraws with fresh numbers: tabs drawn earlier in
the same run would still show the old data. But a rerun wipes everything on
the page, including "Saved!" messages. So: put the message in session_state
(which survives reruns), rerun, and show it at the top of the next run.
"""

import streamlit as st


def rerun_with(toast: str | None = None) -> None:
    """Start the page over, showing `toast` as a pop-up on the next run."""
    if toast:
        st.session_state.setdefault("toasts", []).append(toast)
    st.rerun()


def show_toasts() -> None:
    """Show (once) any pop-ups saved before the last rerun. Called at the top of app.py."""
    for message in st.session_state.pop("toasts", []):
        st.toast(message)


def keep_results(card: str, results: list[tuple[str, str]]) -> None:
    """Save a card's result lines, like ("success", "Chase1234.csv: 52 new"), for after the rerun."""
    st.session_state[f"results-{card}"] = results


def show_results(card: str) -> None:
    """Show (once) a card's saved result lines, in their colors."""
    for kind, text in st.session_state.pop(f"results-{card}", []):
        getattr(st, kind)(text)  # st.success / st.error / st.info / st.caption
