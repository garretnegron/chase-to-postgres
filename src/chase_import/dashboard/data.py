"""Reading from (and later writing to) Postgres."""

import os

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


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
