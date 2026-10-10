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


CREATE TABLE IF NOT EXISTS categories (
    subcategory     text PRIMARY KEY,
    category        text NOT NULL,
    tax_relevant    boolean NOT NULL DEFAULT false,
    is_spending     boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS category_rules (
    id              serial PRIMARY KEY,
    pattern         text NOT NULL,
    min_spent       numeric(12, 2),  -- optional: only applies if at least this much was spent
    subcategory     text NOT NULL REFERENCES categories (subcategory) ON UPDATE CASCADE,
    priority        integer NOT NULL DEFAULT 100,
    UNIQUE NULLS NOT DISTINCT (pattern, min_spent)
);


CREATE TABLE IF NOT EXISTS category_overrides (
    row_hash       text PRIMARY KEY, -- overrides must survive trunc and load.
    subcategory    text NOT NULL REFERENCES categories (subcategory) ON UPDATE CASCADE,
    note           text,
    created_at     timestamptz NOT NULL DEFAULT now()
);


CREATE TABLE IF NOT EXISTS merchant_categories (
    merchant        text PRIMARY KEY,
    subcategory     text NOT NULL REFERENCES categories (subcategory) ON UPDATE CASCADE,
    created_at      timestamptz NOT NULL DEFAULT now()
);


-- One definition of "merchant": the description without the trailing MM/DD
-- purchase date. Used by the view, by categorize, and in your own queries.
CREATE OR REPLACE FUNCTION merchant_name(description text) RETURNS text
    LANGUAGE sql IMMUTABLE
    RETURN regexp_replace(description, '\s\d{2}/\d{2}$', '');


CREATE OR REPLACE VIEW transactions_categorized AS
SELECT
    t.id,
    coalesce(t.transaction_date, t.posted_date)  AS date,
    a.nickname                                    AS account,
    t.description,
    t.amount,
    c.category,
    c.subcategory,
    c.is_spending,
    c.tax_relevant,
    CASE
        WHEN o.subcategory         IS NOT NULL THEN 'manual'
        WHEN best_rule.subcategory IS NOT NULL THEN 'rule'
        WHEN m.subcategory         IS NOT NULL THEN 'ai'
    END                                           AS category_source,
    t.row_hash,
    merchant_name(t.description)                  AS merchant
FROM transactions t
JOIN accounts a ON a.id = t.account_id
LEFT JOIN category_overrides o ON o.row_hash = t.row_hash
LEFT JOIN LATERAL (
    SELECT r.subcategory
    FROM category_rules r
    WHERE t.description ILIKE r.pattern
      AND (r.min_spent IS NULL OR -t.amount >= r.min_spent)
    ORDER BY r.priority, r.id
    LIMIT 1
) best_rule ON true
LEFT JOIN merchant_categories m ON m.merchant = merchant_name(t.description)
JOIN categories c
  ON c.subcategory = coalesce(o.subcategory, best_rule.subcategory, m.subcategory, 'Uncategorized');
