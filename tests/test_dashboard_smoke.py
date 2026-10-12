"""Run the whole dashboard against a real, empty scratch database.

Skipped unless CHASE_TEST_DATABASE_URL points at one. GitHub's test machines set
it (see .github/workflows/test.yml); on your own computer you normally won't,
so your real database is never touched by tests.

Streamlit's AppTest runs app.py the way a browser visit would, top to bottom,
every tab, and records any error instead of drawing it.
"""

import os
from pathlib import Path

import pytest

URL = os.environ.get("CHASE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="set CHASE_TEST_DATABASE_URL to an empty scratch database")

APP = Path(__file__).parents[1] / "src" / "chase_import" / "dashboard" / "app.py"
SAMPLES = Path(__file__).parent / "sample_data"
# Any of the starter lists will do
STARTER_LIST = sorted((Path(__file__).parents[1] / "starter_lists").glob("*.csv"))[0]
CHASE_FILES = [
    "Chase1234_Activity_20261004.CSV",
    "Chase1234_Activity_20261009.CSV",
    "Chase5678_Activity20260901_20260930_20261009.CSV",
]


def run_dashboard():
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    st.cache_data.clear()  # each run should read the database fresh
    app = AppTest.from_file(str(APP), default_timeout=60)
    app.run()
    assert not app.exception, [str(e) for e in app.exception]
    return app


def test_dashboard_from_empty_database_to_full(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", URL)
    import pandas as pd

    from chase_import import db
    from chase_import import parser as p
    from chase_import.category_list import plan_changes, read_file

    with db.connect(URL) as conn:
        db.init_schema(conn)
        if conn.execute("SELECT count(*) FROM transactions").fetchone()[0]:
            pytest.skip("the test database isn't empty")

    # Day one: no categories, no data -> the welcome page.
    app = run_dashboard()
    assert "Welcome" in app.title[0].value

    # Do what the welcome page's steps do: load Chase files, upload a category list.
    with db.connect(URL) as conn:
        for name in CHASE_FILES:
            db.load_file(conn, p.parse_file(SAMPLES / name))
        existing = pd.DataFrame(
            conn.execute("SELECT subcategory, category, is_spending, is_income, tax_relevant "
                         "FROM categories").fetchall(),
            columns=["subcategory", "category", "is_spending", "is_income", "tax_relevant"],
        )
        plan = plan_changes(read_file(STARTER_LIST.name, STARTER_LIST.read_bytes()), existing)
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO categories (subcategory, category, is_spending, is_income, tax_relevant) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (subcategory) DO NOTHING",
                plan.new,
            )

    # Now the full dashboard, every tab.
    app = run_dashboard()
    assert app.title[0].value.endswith("Spending")
    assert [tab.label for tab in app.tabs] == ["Import", "Overview", "Categories", "Review", "Settings"]
