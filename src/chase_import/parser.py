"""Read Chase activity exports (CSV, Excel or Parquet) into normalized rows.

Chase has two export layouts:

  Checking / savings:
    Details, Posting Date, Description, Amount, Type, Balance, Check or Slip #

  Credit card:
    Transaction Date, Post Date, Description, Category, Type, Amount, Memo

Each normalized row also gets a ``row_hash`` so the same transaction is never
stored twice, even when two downloads cover overlapping date ranges.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

CHECKING = "checking"
CREDIT_CARD = "credit_card"

SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".xls", ".parquet"}

# Chase names downloads like "Chase1234_Activity_20261009.CSV" or
# "Chase5678_Activity20260101_20260131_20261009.CSV".
_LAST4_IN_FILENAME = re.compile(r"chase(\d{4})", re.IGNORECASE)


class ParseError(ValueError):
    """The file isn't a Chase export we recognize, or a value is malformed."""


@dataclass
class Transaction:
    posted_date: date
    description: str
    amount: Decimal
    transaction_date: date | None = None
    category: str | None = None
    type: str | None = None
    details: str | None = None
    balance: Decimal | None = None
    check_number: str | None = None
    memo: str | None = None
    row_hash: str = ""


@dataclass
class ParsedFile:
    path: Path
    kind: str
    account_last4: str | None
    transactions: list[Transaction] = field(default_factory=list)
    pending_skipped: int = 0


# ---------------------------------------------------------------- reading


def read_table(path: Path) -> pd.DataFrame:
    """Load a file as a DataFrame of strings with trimmed column names."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = _read_chase_csv(path)
    elif suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(path, dtype=object)
    elif suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        raise ParseError(f"{path.name}: unsupported file type {suffix!r}")

    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c and not c.startswith("Unnamed")]]
    # Drop fully empty rows (blank lines at the end of some exports).
    df = df.dropna(how="all")
    df = df[~df.apply(lambda r: all(_blank(v) for v in r), axis=1)]
    return df


def _read_chase_csv(path: Path) -> pd.DataFrame:
    """Read a CSV, allowing the trailing comma Chase puts on checking rows.

    Extra fields are only dropped when they're empty; anything else means the
    file isn't laid out the way we expect, so we stop rather than guess.
    """
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        raise ParseError(f"{path.name}: file is empty")
    header = [h.strip() for h in rows[0]]
    while header and header[-1] == "":
        header.pop()
    width = len(header)
    records = []
    for lineno, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        if any(cell.strip() for cell in row[width:]):
            raise ParseError(
                f"{path.name}, line {lineno}: more values than columns "
                f"({len(row)} vs {width})"
            )
        records.append((row + [""] * width)[:width])
    return pd.DataFrame(records, columns=header, dtype=object)


def detect_kind(columns) -> str:
    cols = set(columns)
    if {"Posting Date", "Description", "Amount"} <= cols:
        return CHECKING
    if {"Transaction Date", "Post Date", "Description", "Amount"} <= cols:
        return CREDIT_CARD
    raise ParseError(
        "columns don't match a Chase checking or credit card export: "
        + ", ".join(sorted(cols))
    )


def last4_from_filename(path: Path) -> str | None:
    m = _LAST4_IN_FILENAME.search(path.name)
    return m.group(1) if m else None


# ---------------------------------------------------------------- values


def _blank(v) -> bool:
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return str(v).strip() == ""


def _text(v) -> str | None:
    return None if _blank(v) else str(v).strip()


def _description(v) -> str:
    """Description with runs of spaces squeezed to one.

    Chase pads descriptions with long runs of spaces ("POS DEBIT        SHOP").
    Only whitespace changes; every word and character is kept.
    """
    return " ".join(str(v).split()) if not _blank(v) else ""


def _date(v, column: str) -> date | None:
    if _blank(v):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ParseError(f"bad date in {column!r}: {s!r}")


def _money(v, column: str) -> Decimal | None:
    if _blank(v):
        return None
    s = str(v).strip().replace("$", "").replace(",", "")
    if s.startswith("(") and s.endswith(")"):  # (12.34) accounting style
        s = "-" + s[1:-1]
    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ParseError(f"bad amount in {column!r}: {v!r}") from None


# Card purchases in checking exports end with the swipe date: "... VERONA NJ 12/31"
_PURCHASE_DATE_AT_END = re.compile(r"\s(\d{2})/(\d{2})$")


def purchase_date_from_description(description: str, posted: date) -> date | None:
    """The MM/DD at the end of a checking description, as a full date.

    The year is taken from the posted date, stepping back a year when needed
    (bought 12/31, posted 01/02/2026 -> 2025-12-31). Anything that doesn't look
    like a real purchase date in the month before posting is ignored, so
    deposits, Zelles and transfers simply have no purchase date.
    """
    m = _PURCHASE_DATE_AT_END.search(description)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    for year in (posted.year, posted.year - 1):
        try:
            d = date(year, month, day)
        except ValueError:  # 13/45, or 02/29 in a non-leap year
            continue
        if 0 <= (posted - d).days <= 31:
            return d
    return None


# ---------------------------------------------------------------- parsing


def _row_to_txn(kind: str, row) -> Transaction:
    if kind == CHECKING:
        posted = _date(row.get("Posting Date"), "Posting Date")
        description = _description(row.get("Description"))
        return Transaction(
            posted_date=posted,
            transaction_date=(
                purchase_date_from_description(description, posted) if posted else None
            ),
            description=description,
            amount=_money(row.get("Amount"), "Amount"),
            type=_text(row.get("Type")),
            details=_text(row.get("Details")),
            balance=_money(row.get("Balance"), "Balance"),
            check_number=_text(row.get("Check or Slip #")),
        )
    return Transaction(
        posted_date=_date(row.get("Post Date"), "Post Date"),
        transaction_date=_date(row.get("Transaction Date"), "Transaction Date"),
        description=_description(row.get("Description")),
        amount=_money(row.get("Amount"), "Amount"),
        category=_text(row.get("Category")),
        type=_text(row.get("Type")),
        memo=_text(row.get("Memo")),
    )


def _assign_hashes(account_last4: str, kind: str, txns: list[Transaction]) -> None:
    """Give each transaction a stable fingerprint.

    Chase exports carry no transaction ID, and two genuinely separate charges
    can look identical (two $4.50 coffees on the same day). So the fingerprint
    is the transaction's fields plus "this is the Nth identical row in the
    file". The same two coffees in an overlapping download get the same two
    fingerprints, so neither is double-counted and neither is lost.
    """
    seen: Counter[str] = Counter()
    for t in txns:
        base = "|".join(
            [
                account_last4,
                kind,
                t.posted_date.isoformat(),
                t.transaction_date.isoformat() if t.transaction_date else "",
                t.description,
                str(t.amount),
            ]
        )
        seen[base] += 1
        t.row_hash = hashlib.sha256(f"{base}|{seen[base]}".encode()).hexdigest()


def parse_file(path: Path | str, account_last4: str | None = None) -> ParsedFile:
    path = Path(path)
    df = read_table(path)
    kind = detect_kind(df.columns)
    last4 = account_last4 or last4_from_filename(path)

    txns: list[Transaction] = []
    pending = 0
    for i, row in enumerate(df.to_dict("records"), start=2):  # row 1 = header
        try:
            t = _row_to_txn(kind, row)
        except ParseError as e:
            raise ParseError(f"{path.name}, line {i}: {e}") from None
        if t.posted_date is None or t.amount is None:
            raise ParseError(f"{path.name}, line {i}: missing date or amount")
        # Pending checking rows have no running balance yet. They can still
        # change before they post (tips, holds, dates), which would give the
        # posted version a different fingerprint and double-count it. Skip
        # them; they arrive in a later download once posted.
        if kind == CHECKING and t.balance is None:
            pending += 1
            continue
        txns.append(t)

    # Chase lists newest first; store oldest first so occurrence numbering
    # doesn't depend on how far back a download goes.
    txns.sort(key=lambda t: (t.posted_date, t.transaction_date or t.posted_date))

    parsed = ParsedFile(
        path=path,
        kind=kind,
        account_last4=last4,
        transactions=txns,
        pending_skipped=pending,
    )
    if last4:
        _assign_hashes(last4, kind, txns)
    return parsed


def find_files(paths) -> list[Path]:
    """Expand folders into the supported files inside them."""
    out: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            out.extend(
                sorted(f for f in p.iterdir() if f.suffix.lower() in SUPPORTED_SUFFIXES)
            )
        elif p.exists():
            out.append(p)
        else:
            raise FileNotFoundError(p)
    return out
