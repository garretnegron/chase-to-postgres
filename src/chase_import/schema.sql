-- Safe to run more than once.

CREATE TABLE IF NOT EXISTS accounts (
    id          serial PRIMARY KEY,
    last4       text NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('checking', 'credit_card')),
    nickname    text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (last4, kind)
);

CREATE TABLE IF NOT EXISTS transactions (
    id                bigserial PRIMARY KEY,
    account_id        integer NOT NULL REFERENCES accounts (id),
    transaction_date  date,              -- swipe date: credit cards, and checking card purchases
    posted_date       date NOT NULL,
    description       text NOT NULL,
    amount            numeric(12, 2) NOT NULL,  -- negative = money out
    category          text,              -- credit cards only (Chase's category)
    type              text,
    details           text,              -- checking only: DEBIT / CREDIT / CHECK / DSLIP
    balance           numeric(12, 2),    -- checking only: running balance
    check_number      text,              -- checking only
    memo              text,              -- credit cards only
    source_file       text NOT NULL,
    row_hash          text NOT NULL UNIQUE,
    imported_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS transactions_account_date_idx
    ON transactions (account_id, posted_date);

-- One row per transaction with a single "date" column and the account name,
-- handy for queries and spreadsheets.
CREATE OR REPLACE VIEW all_transactions AS
SELECT
    t.id,
    coalesce(t.transaction_date, t.posted_date) AS date,
    coalesce(a.nickname, a.kind || ' ' || a.last4) AS account,
    a.kind AS account_kind,
    t.description,
    t.amount,
    t.category,
    t.type,
    t.balance,
    t.posted_date,
    t.source_file
FROM transactions t
JOIN accounts a ON a.id = t.account_id;
