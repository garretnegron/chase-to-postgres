"""Tests for reading and planning category spreadsheets (no database needed)."""

import pandas as pd
import pytest

from chase_import.category_list import (
    CategoryFileError, parse_flag, plan_changes, read_file, template, to_excel_bytes, to_sheet,
)

EXISTING = pd.DataFrame(
    [
        ("Groceries", "Food & Drink", True, False),
        ("Paycheck", "Income", False, False),
        ("Uncategorized", "Other", True, False),
    ],
    columns=["subcategory", "category", "is_spending", "tax_relevant"],
)


def csv(text: str) -> pd.DataFrame:
    return read_file("list.csv", text.encode("utf-8"))


def test_flags():
    assert parse_flag("Yes", default=False) is True
    assert parse_flag(" x ", default=False) is True
    assert parse_flag("0", default=True) is False
    assert parse_flag("", default=True) is True
    assert parse_flag("maybe", default=True) is None


def test_loose_headers_and_optional_flags():
    df = csv("category group,Sub Category\nHome,Rent\n")
    plan = plan_changes(df, EXISTING)
    assert plan.new == [("Rent", "Home", True, False)]  # flags fall back to defaults


def test_new_changed_unchanged():
    df = csv(
        "Group,Subcategory,Counts as spending,Tax-relevant\n"
        "Food & Drink,Groceries,yes,no\n"  # same as now
        "Money In,paycheck,no,no\n"  # different group; different case
        "Pets,Vet Care,yes,no\n"  # new
    )
    plan = plan_changes(df, EXISTING)
    assert plan.unchanged == 1
    assert plan.changed == [("Paycheck", "Money In", False, False)]  # keeps your spelling
    assert plan.new == [("Vet Care", "Pets", True, False)]
    assert plan.problems == []


def test_problems_are_reported_not_applied():
    df = csv(
        "Group,Subcategory,Counts as spending\n"
        "Pets,Vet Care,yes\n"
        "Pets,vet care,yes\n"  # duplicate (row 3)
        ",Orphan,yes\n"  # no group (row 4)
        "Pets,Grooming,sometimes\n"  # bad flag (row 5)
        ",,\n"  # blank line: ignored quietly
    )
    plan = plan_changes(df, EXISTING)
    assert [p.split(":")[0] for p in plan.problems] == ["Row 3", "Row 4", "Row 5"]
    assert plan.to_apply == [("Vet Care", "Pets", True, False)]


def test_missing_columns():
    with pytest.raises(CategoryFileError, match="Group"):
        csv("Name,Amount\nRent,5\n")


def test_wrong_file_type():
    with pytest.raises(CategoryFileError):
        read_file("list.pdf", b"%PDF")


def test_excel_round_trip():
    """Export your list, read it back: nothing should change."""
    data = to_excel_bytes(to_sheet(EXISTING))
    plan = plan_changes(read_file("mine.xlsx", data), EXISTING)
    assert plan.unchanged == 3 and plan.to_apply == [] and plan.problems == []


def test_template_is_valid():
    plan = plan_changes(read_file("t.xlsx", to_excel_bytes(template())), EXISTING)
    # Groceries and Paycheck already exist (same settings); the other two are new
    assert len(plan.new) == 2 and plan.unchanged == 2 and plan.problems == []


def test_excel_csv_with_byte_order_mark():
    """Excel's "CSV UTF-8" puts an invisible marker before the first header."""
    df = read_file("x.csv", "﻿Group,Subcategory\nHome,Rent\n".encode("utf-8"))
    assert plan_changes(df, EXISTING).new == [("Rent", "Home", True, False)]
