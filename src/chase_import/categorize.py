"""Categorize leftover merchants with Claude and save the answers."""

from __future__ import annotations

import json

import anthropic
import psycopg

MODEL = "claude-haiku-5-5"
BATCH_SIZE=50

def uncategorized_merchants(conn: psycopg.Connection) -> list[str]:
    """Merchants that no override, rule or saved AI answer covers yet."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT merchant
            FROM transactions_categorized
            WHERE category_source IS NULL
            GROUP BY merchant
            ORDER BY sum(abs(amount)) DESC
            """
        )
        return [row[0] for row in cur.fetchall()]

def load_categories(conn: psycopg.Connection) -> dict[str, str]:
    """Your categories as {subcategory: group}, e.g. {'Gas': 'Gas', 'Hockey': 'Entertainment'}."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT subcategory, category FROM categories ORDER BY category, subcategory"
        )
        return dict(cur.fetchall())


PROMPT = """You categorize bank transaction descriptions for a personal budget.

Pick exactly one subcategory for each description from this list (its group is in parentheses):
{choices}

If you can't tell what a description is, answer "Uncategorized" rather than guessing.

Reply with only a JSON object that maps each description, exactly as given, to its
subcategory. No other text.

Descriptions:
{merchants}"""


def ask_claude(
    client: anthropic.Anthropic, merchants: list[str], categories: dict[str, str]
) -> dict[str, str]:
    """Categorize one batch. Returns {merchant: subcategory}, keeping only valid answers."""
    choices = "\n".join(f"- {sub} ({group})" for sub, group in categories.items())
    prompt = PROMPT.format(choices=choices, merchants="\n".join(merchants))

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    start, end = text.find("{"), text.rfind("}")
    answers = json.loads(text[start : end + 1])

    return {
        merchant: sub
        for merchant, sub in answers.items()
        if merchant in merchants and sub in categories and sub != "Uncategorized"
    }


def save_answers(conn: psycopg.Connection, answers: dict[str, str]) -> int:
    """Store answers in merchant_categories. Returns how many were saved."""
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO merchant_categories (merchant, subcategory)
            VALUES (%s, %s)
            ON CONFLICT (merchant) DO NOTHING
            """,
            list(answers.items()),
        )
    conn.commit()
    return len(answers)


def run(conn: psycopg.Connection, dry_run: bool = False, limit: int | None = None) -> dict[str, str]:
    """Categorize all uncategorized merchants. Returns every answer found."""
    merchants = uncategorized_merchants(conn)[:limit]
    categories = load_categories(conn)
    client = anthropic.Anthropic()

    found: dict[str, str] = {}
    for start in range(0, len(merchants), BATCH_SIZE):
        batch = merchants[start : start + BATCH_SIZE]
        answers = ask_claude(client, batch, categories)
        if not dry_run:
            save_answers(conn, answers)
        found.update(answers)
        print(f"  batch {start // BATCH_SIZE + 1}: {len(answers)} of {len(batch)} categorized")
    return found