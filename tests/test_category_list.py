"""Tests for reading and planning category spreadsheets (no database needed)."""

import pandas as pd
import pytest

from chase_import.category_list import (
    CategoryFileError, parse_flag, plan_changes, read_file, template, to_excel_bytes, to_sheet,
)

EXISTING = pd.DataFrame(
    [
        ("Groceries", "Food & Drink", True, False, False),
        ("Paycheck", "Income", False, True, False),
        ("Uncategorized", "Other", True, False, False),
    ],
    columns=["subcategory", "category", "is_spending", "is_income", "tax_relevant"],
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
    assert plan.new == [("Rent", "Home", True, False, False)]  # flags fall back to defaults


def test_new_changed_unchanged():
    df = csv(
        "Group,Subcategory,Counts as spending,Tax-relevant\n"
        "Food & Drink,Groceries,yes,no\n"  # same as now
        "Money In,paycheck,no,\n"  # different group; different case; blank tax = keep
        "Pets,Vet Care,yes,no\n"  # new
    )
    plan = plan_changes(df, EXISTING)
    assert plan.unchanged == 1
    assert plan.changed == [("Paycheck", "Money In", False, True, False)]  # keeps spelling and income
    assert plan.new == [("Vet Care", "Pets", True, False, False)]
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
    assert plan.to_apply == [("Vet Care", "Pets", True, False, False)]


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
    # Groceries and Paycheck already exist (same settings); the other three are new
    assert len(plan.new) == 3 and plan.unchanged == 2 and plan.problems == []


def test_excel_csv_with_byte_order_mark():
    """Excel's "CSV UTF-8" puts an invisible marker before the first header."""
    df = read_file("x.csv", "﻿Group,Subcategory\nHome,Rent\n".encode("utf-8"))
    assert plan_changes(df, EXISTING).new == [("Rent", "Home", True, False, False)]


def test_old_file_without_income_column_keeps_income():
    """A file from before "Is income" existed must not switch income off."""
    df = csv("Group,Subcategory,Counts as spending,Tax-relevant\nIncome,Paycheck,no,no\n")
    plan = plan_changes(df, EXISTING)
    assert plan.unchanged == 1 and plan.to_apply == []


def test_spending_and_income_together_is_a_problem():
    df = csv("Group,Subcategory,Counts as spending,Is income\nOdd,Side Gig,yes,yes\n")
    plan = plan_changes(df, EXISTING)
    assert plan.to_apply == [] and "both spending and income" in plan.problems[0]
