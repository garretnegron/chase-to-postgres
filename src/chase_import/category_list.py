"""Category lists as spreadsheets: read one, check it, and plan what it changes.

No Streamlit and no database in here, so it's easy to test. The dashboard's
Settings tab shows the plan and the database code applies it.

A category file has one row per subcategory:

    Group         | Subcategory | Counts as spending | Is income | Tax-relevant
    Food & Drink  | Groceries   | yes                | no        | no
    Income        | Paycheck    | no                 | yes       | no

The three yes/no columns are optional. Left out (or left blank), a subcategory
you already have keeps its current setting, and a new one gets the default.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import pandas as pd

COLUMNS = ["Group", "Subcategory", "Counts as spending", "Is income", "Tax-relevant"]
FLAGS = ("is_spending", "is_income", "tax_relevant")
DEFAULTS = {"is_spending": True, "is_income": False, "tax_relevant": False}

# Header spellings people actually use, after lowercasing and dropping
# everything that isn't a letter: "Sub Category" -> "subcategory".
HEADER_NAMES = {
    "group": "category", "category": "category", "categorygroup": "category",
    "subcategory": "subcategory", "sub": "subcategory", "name": "subcategory",
    "countsasspending": "is_spending", "isspending": "is_spending", "spending": "is_spending",
    "isincome": "is_income", "income": "is_income", "countsasincome": "is_income",
    "taxrelevant": "tax_relevant", "tax": "tax_relevant", "taxable": "tax_relevant",
}
YES = {"yes", "y", "true", "t", "1", "x"}
NO = {"no", "n", "false", "f", "0"}


class CategoryFileError(ValueError):
    """The file can't be used at all (wrong type, missing columns)."""


@dataclass
class Plan:
    """What applying a file would do. Nothing is written until it's applied."""

    new: list[tuple] = field(default_factory=list)  # (subcategory, group, is_spending, is_income, tax_relevant)
    changed: list[tuple] = field(default_factory=list)  # same shape, rows that already exist
    unchanged: int = 0
    problems: list[str] = field(default_factory=list)  # rows that were skipped, and why

    @property
    def to_apply(self) -> list[tuple]:
        return self.new + self.changed


def read_file(filename: str, data: bytes) -> pd.DataFrame:
    """Read an uploaded .csv or .xlsx into a DataFrame of plain text."""
    suffix = filename.lower().rsplit(".", 1)[-1]
    if suffix == "csv":
        df = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False,
                         encoding="utf-8-sig")  # utf-8-sig: Excel's CSVs start with a hidden marker
    elif suffix in ("xlsx", "xlsm"):
        df = pd.read_excel(io.BytesIO(data), dtype=str, keep_default_na=False)
    else:
        raise CategoryFileError("Use a .csv or .xlsx file.")
    return _rename_headers(df)


def _rename_headers(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for col in df.columns:
        key = re.sub(r"[^a-z]", "", str(col).lower())
        if key in HEADER_NAMES and HEADER_NAMES[key] not in renamed.values():
            renamed[col] = HEADER_NAMES[key]
    df = df.rename(columns=renamed)
    missing = [c for c, label in (("category", "Group"), ("subcategory", "Subcategory"))
               if c not in df.columns]
    if missing:
        names = {"category": "Group", "subcategory": "Subcategory"}
        raise CategoryFileError(
            "The file needs columns named " + " and ".join(names[c] for c in missing)
            + f". Found: {', '.join(map(str, df.columns)) or 'nothing'}."
        )
    return df


def parse_flag(value, default: bool) -> bool | None:
    """yes/no, true/false, 1/0 or x -> True/False. Blank -> default. Anything else -> None."""
    text = str(value).strip().lower()
    if text == "" or text == "nan":
        return default
    if text in YES:
        return True
    if text in NO:
        return False
    return None


def plan_changes(df: pd.DataFrame, existing: pd.DataFrame) -> Plan:
    """Compare the file with the categories you already have.

    `existing` has columns subcategory, category, is_spending, is_income, tax_relevant.
    New subcategories are added, ones that differ are updated, and nothing is
    ever deleted: removing goes through Settings so its rules have somewhere to go.
    Names match ignoring case, keeping the spelling you already have.
    """
    current = {
        row.subcategory.lower(): (row.subcategory, row.category,
                                  bool(row.is_spending), bool(row.is_income), bool(row.tax_relevant))
        for row in existing.itertuples()
    }
    plan = Plan()
    seen: dict[str, int] = {}

    for i, row in enumerate(df.to_dict("records")):
        line = i + 2  # spreadsheet row number: row 1 is the header
        sub = str(row.get("subcategory", "")).strip()
        group = str(row.get("category", "")).strip()
        if not sub and not group:
            continue  # empty line, nothing to say
        if not sub or not group:
            plan.problems.append(f"Row {line}: needs both a group and a subcategory.")
            continue
        if sub.lower() in seen:
            plan.problems.append(f"Row {line}: '{sub}' is already on row {seen[sub.lower()]}, so this one was skipped.")
            continue
        seen[sub.lower()] = line

        # A blank (or missing) yes/no keeps what an existing subcategory has now;
        # a new subcategory gets the default.
        before = current.get(sub.lower())
        fallback = dict(zip(FLAGS, before[2:])) if before else DEFAULTS
        flags = [parse_flag(row.get(flag, ""), default=fallback[flag]) for flag in FLAGS]
        if None in flags:
            plan.problems.append(f"Row {line}: '{sub}' has a yes/no column that isn't yes or no.")
            continue
        spending, income, tax = flags
        if spending and income:
            plan.problems.append(f"Row {line}: '{sub}' can't be both spending and income.")
            continue

        if before is None:
            plan.new.append((sub, group, spending, income, tax))
            continue
        name, *now = before
        if now == [group, spending, income, tax]:
            plan.unchanged += 1
        else:
            plan.changed.append((name, group, spending, income, tax))
    return plan


def to_sheet(existing: pd.DataFrame) -> pd.DataFrame:
    """Your categories in the file's layout, ready to download."""
    yes_no = {True: "yes", False: "no"}
    return pd.DataFrame({
        "Group": existing["category"],
        "Subcategory": existing["subcategory"],
        "Counts as spending": existing["is_spending"].map(yes_no),
        "Is income": existing["is_income"].map(yes_no),
        "Tax-relevant": existing["tax_relevant"].map(yes_no),
    })


def template() -> pd.DataFrame:
    """A small example to fill in."""
    return pd.DataFrame(
        [
            ["Food & Drink", "Groceries", "yes", "no", "no"],
            ["Food & Drink", "Restaurants", "yes", "no", "no"],
            ["Income", "Paycheck", "no", "yes", "no"],
            ["Money Movement", "Credit Card Payment", "no", "no", "no"],
            ["Education", "Tuition", "yes", "no", "yes"],
        ],
        columns=COLUMNS,
    )


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    """A DataFrame as an .xlsx file, in memory, for a download button."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Categories")
        sheet = writer.sheets["Categories"]
        for letter, width in zip("ABCDE", (22, 30, 20, 12, 14)):
            sheet.column_dimensions[letter].width = width
    return buffer.getvalue()
