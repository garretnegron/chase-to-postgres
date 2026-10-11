"""Colors, card styling and number formatting shared by every tab."""

from dataclasses import dataclass

import pandas as pd
import streamlit as st

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
