"""Parser tests. The sample files are made-up data in Chase's export format.

Run with:  pytest
"""

from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from chase_import import parser as p

DATA = Path(__file__).parent / "sample_data"
CHECKING_1 = DATA / "Chase1234_Activity_20261004.CSV"
CHECKING_2 = DATA / "Chase1234_Activity_20261009.CSV"
CARD = DATA / "Chase5678_Activity20260901_20260930_20261009.CSV"


def test_checking_trailing_comma_and_columns():
    f = p.parse_file(CHECKING_1)
    assert f.kind == p.CHECKING
    assert f.account_last4 == "1234"
    assert len(f.transactions) == 4
    payroll = [t for t in f.transactions if "PAYROLL" in t.description][0]
    assert payroll.amount == Decimal("1500.00")
    assert payroll.balance == Decimal("1400.00")
    assert payroll.details == "CREDIT"
    check = [t for t in f.transactions if t.check_number][0]
    assert check.check_number == "1001"
    assert check.amount == Decimal("-200.00")


def test_identical_rows_are_both_kept():
    f = p.parse_file(CHECKING_1)
    coffees = [t for t in f.transactions if "COFFEE" in t.description]
    assert len(coffees) == 2
    assert coffees[0].row_hash != coffees[1].row_hash


def test_overlapping_downloads_produce_matching_hashes():
    a = {t.row_hash for t in p.parse_file(CHECKING_1).transactions}
    b = {t.row_hash for t in p.parse_file(CHECKING_2).transactions}
    assert len(a & b) == 2  # the two coffees on 10/03
    assert len(a | b) == 6  # 4 + 4 - 2 overlap


def test_credit_card():
    f = p.parse_file(CARD)
    assert f.kind == p.CREDIT_CARD
    assert f.account_last4 == "5678"
    assert len(f.transactions) == 5
    flight = [t for t in f.transactions if t.description == "AIRLINE TICKET"][0]
    assert str(flight.transaction_date) == "2026-09-28"
    assert str(flight.posted_date) == "2026-09-29"
    assert flight.category == "Travel"
    assert flight.amount == Decimal("-312.40")
    payment = [t for t in f.transactions if t.type == "Payment"][0]
    assert payment.category is None


def test_account_from_flag_when_not_in_filename():
    f = p.parse_file(DATA / "card_export.csv")
    assert f.account_last4 is None
    f = p.parse_file(DATA / "card_export.csv", account_last4="5678")
    assert f.account_last4 == "5678"
    # same data, same account -> same fingerprints as the named file
    assert {t.row_hash for t in f.transactions} == {
        t.row_hash for t in p.parse_file(CARD).transactions
    }


def test_rejects_non_chase_file():
    with pytest.raises(p.ParseError):
        p.parse_file(DATA / "not_chase.csv")


def test_excel_matches_csv(tmp_path):
    xlsx = tmp_path / "Chase5678_activity.xlsx"
    pd.read_csv(CARD, dtype=str, keep_default_na=False).to_excel(xlsx, index=False)
    assert [t.row_hash for t in p.parse_file(xlsx).transactions] == [
        t.row_hash for t in p.parse_file(CARD).transactions
    ]


def test_excel_with_real_dates_and_numbers(tmp_path):
    df = pd.read_csv(CARD)
    df["Transaction Date"] = pd.to_datetime(df["Transaction Date"])
    df["Post Date"] = pd.to_datetime(df["Post Date"])
    xlsx = tmp_path / "Chase5678_activity.xlsx"
    df.to_excel(xlsx, index=False)
    assert [t.row_hash for t in p.parse_file(xlsx).transactions] == [
        t.row_hash for t in p.parse_file(CARD).transactions
    ]


def test_parquet_matches_csv(tmp_path):
    pytest.importorskip("pyarrow")
    pq = tmp_path / "Chase5678_activity.parquet"
    pd.read_csv(CARD, dtype=str, keep_default_na=False).to_parquet(pq)
    assert [t.row_hash for t in p.parse_file(pq).transactions] == [
        t.row_hash for t in p.parse_file(CARD).transactions
    ]


def test_pending_checking_rows_are_skipped(tmp_path):
    f = tmp_path / "Chase1234_Activity_20261010.csv"
    f.write_text(
        "Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #\n"
        "DEBIT,10/09/2026,PENDING CAFE,-3.28,DEBIT_CARD,,,\n"
        "DEBIT,10/08/2026,POSTED CAFE,-5.00,DEBIT_CARD,100.00,,\n"
    )
    parsed = p.parse_file(f)
    assert [t.description for t in parsed.transactions] == ["POSTED CAFE"]
    assert parsed.pending_skipped == 1


def test_description_spaces_are_squeezed():
    f = p.parse_file(CHECKING_1)
    coffee = [t for t in f.transactions if "COFFEE" in t.description][0]
    assert coffee.description == "COFFEE SHOP 123 PPD ID: 1"


def test_purchase_date_from_checking_description():
    from datetime import date

    posted = date(2026, 1, 2)
    f = p.purchase_date_from_description
    assert f("QUICK CHEK CORP FAIRFIELD NJ 01/02", posted) == date(2026, 1, 2)
    # bought on New Year's Eve, posted in January -> previous year
    assert f("TST*VERONA INN Verona NJ 12/31", posted) == date(2025, 12, 31)
    # no date at the end: deposits, Zelle, ACH
    assert f("Zelle payment from ALEXANDER POPE WFCT0ZNGH5DB", posted) is None
    assert f("ROBERT HALF INC. PAYROLL PPD ID: 1941648702", posted) is None
    # numbers that aren't a plausible recent date are ignored
    assert f("SOMETHING 13/45", posted) is None
    assert f("SOMETHING 06/15", posted) is None  # months before posting


def test_checking_rows_get_purchase_date(tmp_path):
    f = tmp_path / "Chase1234_Activity_20260105.csv"
    f.write_text(
        "Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #\n"
        "DEBIT,01/02/2026,TST*VERONA INN Verona NJ            12/31,-40.00,DEBIT_CARD,100.00,,\n"
        "CREDIT,01/02/2026,ROBERT HALF INC. PAYROLL PPD ID: 1,500.00,ACH_CREDIT,140.00,,\n"
    )
    txns = {t.description: t for t in p.parse_file(f).transactions}
    assert str(txns["TST*VERONA INN Verona NJ 12/31"].transaction_date) == "2025-12-31"
    assert txns["ROBERT HALF INC. PAYROLL PPD ID: 1"].transaction_date is None


def test_unexpected_extra_values_are_an_error(tmp_path):
    bad = tmp_path / "Chase1234_bad.csv"
    bad.write_text(
        "Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #\n"
        "DEBIT,10/03/2026,SHOP, INC,-4.50,DEBIT_CARD,1191.00,,\n"
    )
    with pytest.raises(p.ParseError):
        p.parse_file(bad)


def test_money_formats():
    assert p._money("$1,234.50", "x") == Decimal("1234.50")
    assert p._money("(12.34)", "x") == Decimal("-12.34")
    assert p._money(-4.5, "x") == Decimal("-4.50")
    assert p._money("", "x") is None
