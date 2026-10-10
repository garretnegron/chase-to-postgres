"""Postgres side: create tables and load parsed files without duplicates."""

from __future__ import annotations

from importlib.resources import files

import psycopg

from .parser import ParsedFile

COLUMNS = [
    "account_id",
    "transaction_date",
    "posted_date",
    "description",
    "amount",
    "category",
    "type",
    "details",
    "balance",
    "check_number",
    "memo",
    "source_file",
    "row_hash",
]


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url)


def init_schema(conn: psycopg.Connection) -> None:
    sql = files("chase_import").joinpath("schema.sql").read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def get_or_create_account(
    conn: psycopg.Connection, last4: str, kind: str, nickname: str | None = None
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO accounts (last4, kind, nickname)
            VALUES (%s, %s, %s)
            ON CONFLICT (last4, kind)
                DO UPDATE SET nickname = coalesce(EXCLUDED.nickname, accounts.nickname)
            RETURNING id
            """,
            (last4, kind, nickname),
        )
        return cur.fetchone()[0]


def load_file(
    conn: psycopg.Connection, parsed: ParsedFile, nickname: str | None = None
) -> tuple[int, int]:
    """Insert a parsed file. Returns (inserted, already_there).

    Rows are copied into a temporary table first, then moved across with
    ON CONFLICT DO NOTHING, so re-importing a file (or an overlapping one)
    only adds what's new. The whole file goes in or none of it does.
    """
    if not parsed.account_last4:
        raise ValueError(f"{parsed.path.name}: no account number; pass --account")

    with conn.transaction():
        account_id = get_or_create_account(
            conn, parsed.account_last4, parsed.kind, nickname
        )
        cols = ", ".join(COLUMNS)
        with conn.cursor() as cur:
            # Only the columns we fill, with no defaults or constraints copied
            # over, so loading into staging doesn't use up transaction IDs.
            cur.execute(
                f"CREATE TEMP TABLE staging ON COMMIT DROP AS "
                f"SELECT {cols} FROM transactions WITH NO DATA"
            )
            with cur.copy(f"COPY staging ({cols}) FROM STDIN") as copy:
                for t in parsed.transactions:
                    copy.write_row(
                        (
                            account_id,
                            t.transaction_date,
                            t.posted_date,
                            t.description,
                            t.amount,
                            t.category,
                            t.type,
                            t.details,
                            t.balance,
                            t.check_number,
                            t.memo,
                            parsed.path.name,
                            t.row_hash,
                        )
                    )
            cur.execute(
                f"""
                INSERT INTO transactions ({cols})
                SELECT {cols} FROM staging
                ON CONFLICT (row_hash) DO NOTHING
                """
            )
            inserted = cur.rowcount
    return inserted, len(parsed.transactions) - inserted


def summary(conn: psycopg.Connection) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT coalesce(a.nickname, a.kind || ' ' || a.last4),
                   count(t.id),
                   min(coalesce(t.transaction_date, t.posted_date)),
                   max(coalesce(t.transaction_date, t.posted_date))
            FROM accounts a
            LEFT JOIN transactions t ON t.account_id = a.id
            GROUP BY a.id
            ORDER BY 1
            """
        )
        return cur.fetchall()
