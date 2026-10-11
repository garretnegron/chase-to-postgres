# 🏦 chase-to-postgres

Turn your Chase bank and credit card downloads into a clean, categorized Postgres
database you own and can query however you like.

```
> chase-import load data
LOAD  Chase6911_Activity_20261009.csv: 1406 new, 0 already in the database (checking ...6911), 5 pending skipped
Done. 1406 new transactions.

> chase-import categorize
  batch 1: 45 of 50 categorized
  batch 2: 50 of 50 categorized
Done. 95 merchants were categorized.
```

**What it does**

- 📥 **Imports** Chase checking and credit card exports (CSV, Excel or Parquet)
- 🔁 **Never double-counts.** Re-import a file or overlapping downloads as often as you like
- ⏳ **Skips pending transactions** and picks them up once they've posted
- 🗓️ **Finds the real purchase date** hidden in checking descriptions (`... VERONA NJ 12/31`)
- 🏷️ **Categorizes spending** with your own rules first, then Claude (AI) for the leftovers
- ✋ **Lets you override** any single transaction by hand
- 📊 **Shows it all in a dashboard** in your browser: spending by month, top merchants, and a table to fix categories
- 🔒 **Keeps your data local.** Bank files, passwords and keys never go to GitHub

---

## How it works

```mermaid
flowchart LR
    A[Chase CSV] -->|chase-import load| B[(transactions)]
    B --> V{{transactions_categorized view}}
    O[category_overrides<br/>your manual fixes] --> V
    R[category_rules<br/>your patterns] --> V
    M[merchant_categories<br/>Claude's answers] --> V
    B -.->|chase-import categorize<br/>only leftover merchants| M
```

Every transaction gets exactly one category, decided in this order:

| Priority | Source | Example |
|:-:|---|---|
| 1 | **Manual override** (one specific transaction) | "This Affirm payment was a laptop" |
| 2 | **Rule** (a pattern in the description) | `%KRAUSZER%` → Convenience & Coffee |
| 3 | **AI** (Claude's saved answer for that merchant) | `PUBLIX #854 CAPE CORAL FL` → Groceries |
| 4 | **Uncategorized** | anything nobody has decided yet |

The imported `transactions` table is never modified by categorization. Categories
live in their own tables and are combined in a view, so you can change rules or
reload data at any time without losing anything.

---

## Requirements

- **Windows** (instructions below; Mac/Linux work too with the usual command differences)
- **Python 3.10+**
- **PostgreSQL 15 or newer.** The rules table uses a feature added in 15
- **An Anthropic API key**, only for `categorize`. Everything else works without one

---

## One-time setup

### 1. Install Postgres and create the database

Install from <https://www.postgresql.org/download/windows/> (the EDB installer) and
remember the password you set for the `postgres` user. Then open **SQL Shell (psql)**
from the Start menu, press Enter through the prompts, type that password, and run:

```sql
CREATE DATABASE finances;
```

### 2. Get the code and install it

In PowerShell or the VS Code terminal:

```powershell
git clone https://github.com/YOUR_USERNAME/chase-to-postgres.git
cd chase-to-postgres
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dashboard]"
```

The `[dashboard]` part also installs Streamlit for the dashboard. Leave it off
(`pip install -e .`) if you only want the importer.

> If PowerShell refuses to run `activate`, run this once, then try again:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 3. Add your secrets

Copy `.env.example` to `.env` and fill it in:

```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/finances
ANTHROPIC_API_KEY=sk-ant-...
```

`.env` is git-ignored, so neither the password nor the key ever goes to GitHub.

> **Getting an API key:** create a Console account at <https://platform.claude.com>,
> add a few dollars of credit under Billing, then **Settings → API keys → Create key**
> (scope it to the **Default workspace**). The key is shown only once, so copy it
> straight into `.env`. API usage is billed separately from a Claude.ai subscription.
> Categorizing a few hundred merchants costs well under a dollar.

### 4. Create the tables

```powershell
chase-import init
```

### 5. Load your categories and rules

Open each file below in the VS Code **PostgreSQL** extension (connected to `finances`)
or in pgAdmin's **Query Tool**, and run it, **in this order**:

1. `seed_categories.sql`: your list of categories
2. `seed_rules.sql`: your patterns (rules point at categories, so categories go first)

Both are safe to run again any time. The files in this repo are **one person's
lists**, so change them to fit your own spending before you run them.

---

## Everyday use

1. **Download from Chase:** open an account on chase.com, click the **download**
   icon above the transactions, choose **CSV** and a date range. Overlapping
   your last download is fine.
2. **Move the file into the `data` folder** without renaming it. The
   `Chase1234` in the name is how the importer knows which account it is.
3. **Run:**

```powershell
.venv\Scripts\activate
chase-import load data
chase-import categorize
chase-import dashboard
```

That's it. Old files can stay in `data`; re-loading them adds nothing.

### All commands

| Command | What it does |
|---|---|
| `chase-import init` | Create or update the tables (safe to re-run) |
| `chase-import load data` | Import every export in the `data` folder |
| `chase-import load data --dry-run` | Check the files without touching the database |
| `chase-import load file.csv --account 1234` | For a file whose name doesn't contain `Chase1234` |
| `chase-import load file.csv --name "My checking"` | Give the account a friendly name (it sticks) |
| `chase-import summary` | Transaction count and date range per account |
| `chase-import categorize --dry-run --limit 20` | Preview Claude's answers for the 20 biggest uncategorized merchants. Saves nothing |
| `chase-import categorize` | Ask Claude about every uncategorized merchant and save the answers |
| `chase-import dashboard` | Open the dashboard in your browser (Ctrl+C in the terminal to stop it) |

---

## Dashboard

```powershell
chase-import dashboard
```

Opens <http://localhost:8501> in your browser. It runs on your computer only, and
nothing is published. If Windows asks about a firewall, **Cancel** is fine. Stop it
with **Ctrl+C** in the terminal.

The date and account pickers at the top apply to every tab.

| Tab | What it shows |
|---|---|
| **Import** | Pick your Chase downloads and press **Load**, then **Categorize with AI**. The same thing as `load` and `categorize`, without the terminal |
| **Overview** | Spent, average per month, money in, and the difference; spending by month stacked by group; your top merchants |
| **Categories** | Pick one group (say, Food & Drink) to see its subcategories month by month and its top merchants |
| **Review** | A table of transactions you can re-categorize from a dropdown. Filter by who decided (AI, rule, by hand, uncategorized) or search a merchant, change subcategories, then press **Save** |
| **Settings** | Your category list: edit it in a table, import or export it as a spreadsheet, add one, or remove one (you choose where its transactions go) |

Good to know:

- Only **spending** counts in the totals and charts: subcategories with
  `is_spending = false` (income, transfers, card payments) are left out, and
  income shows up in **Money in** instead.
- Each group keeps the same color everywhere. The 7 biggest get their own color,
  and the rest are combined into gray **All other**.
- Fixes saved on the **Review** tab are overrides (see below), so they outrank rules
  and AI and survive reloads.
- The dashboard only uses the columns and flags in `transactions_categorized`, never
  specific category names, so it works with anyone's category list.
- Data refreshes every 60 seconds. After loading new files, wait a minute, or
  press **C** in the browser to clear the cache. Saving on the Review tab refreshes
  right away.

---

## Managing categories

### Categories

**The easy way:** the dashboard's **Settings** tab. To start from a ready-made
list, upload one of the files in `starter_lists/` (or download the blank template
and fill it in). Uploading adds new subcategories and updates changed ones; it
never removes anything.

| Group | Subcategory | Counts as spending | Tax-relevant |
|---|---|---|---|
| Food & Drink | Groceries | yes | no |

**The SQL way:** `seed_categories.sql`, below. Once you manage categories in the
dashboard, the database is the real list and the seed files are just a starting
point for new installs.

#### `seed_categories.sql`

Two levels: a **group** (`Food & Drink`) and a **subcategory** (`Restaurants`).
Each subcategory also has two flags:

- `is_spending`: `false` for Income and Money Movement (transfers, card payments),
  so they don't inflate your spending totals
- `tax_relevant`: `true` for things like tuition or charity, so tax time is one query

Add a row and re-run the file. Renaming a subcategory in the database
automatically updates every rule and override that uses it.

### Rules: `seed_rules.sql`

A rule matches the description with a pattern (`%` means "anything", and case
doesn't matter):

```sql
('%STARBUCKS%',  NULL, 'Convenience & Coffee', 100),
('%WAWA%',       35,   'Gas',                   50),  -- $35 or more at Wawa = gas
('%WAWA%',       NULL, 'Convenience & Coffee', 100),  -- anything less = snacks
('%TAVERN%',     NULL, 'Restaurants',          200),  -- broad keyword, low priority
```

- **`min_spent`** (optional): the rule only applies if at least this much was spent
- **`priority`**: when several rules match, the **lowest number wins**. Give
  specific rules 50–100 and broad keywords 200
- Re-running the file **updates** existing rules to match it. Deleting a line does
  *not* delete the rule, so also run `DELETE FROM category_rules WHERE pattern = '...';`

Tips for good patterns:
- Match the **brand**, not the store: `%STARBUCKS%`, not `%STARBUCKS STORE 21295%`
- Leave out apostrophes (`%MCDONALD%`) or double them (`%KIM''S SUSHI%`)
- Think about what else a short pattern could hit. `%PUB%` also matches **PUB**LIX,
  and `%DELTA%` matches Delta Air Lines

Rules apply **instantly**: add one and every past transaction updates.

### AI: `chase-import categorize`

Sends only the **merchant names** that no rule or override covers (never amounts,
dates or account numbers) to Claude, in batches of 50, and saves the answers.
Claude must pick from your category list. When it isn't sure, nothing is saved,
so the merchant stays visible as uncategorized. Saved answers never change on
their own, and rules and overrides always outrank them.

### Overrides: fix one transaction

The easiest way is the dashboard's **Review** tab. To fix many at once, use SQL:

```sql
-- every visit to one merchant
INSERT INTO category_overrides (row_hash, subcategory, note)
SELECT row_hash, 'Restaurants', 'bar in Hoboken'
FROM transactions_categorized
WHERE merchant = 'MIKE''S WILD MOOSE SALOO HOBOKEN NJ';
```

Use a **rule** when a merchant is always the same thing, and an **override** for a
genuine one-off. Overrides are tied to each transaction's fingerprint, so they
survive reloads.

---

## Useful queries

**How much is categorized?**
```sql
SELECT coalesce(category_source, 'uncategorized') AS source,
       count(*)                                    AS txns,
       sum(-amount) FILTER (WHERE amount < 0)      AS money_out
FROM transactions_categorized
GROUP BY 1;
```

**What's still uncategorized, biggest first?**
```sql
SELECT merchant, count(*) AS visits, sum(amount) AS total
FROM transactions_categorized
WHERE category_source IS NULL
GROUP BY merchant
ORDER BY sum(abs(amount)) DESC;
```

**Spending by month and group**
```sql
SELECT date_trunc('month', date)::date AS month, category, sum(-amount) AS spent
FROM transactions_categorized
WHERE is_spending
GROUP BY 1, 2
ORDER BY 1, 3 DESC;
```

**Tax-relevant spending this year**
```sql
SELECT subcategory, sum(-amount) AS total
FROM transactions_categorized
WHERE tax_relevant AND date >= date_trunc('year', current_date)
GROUP BY subcategory;
```

---

## What's in the database

| Object | What it holds |
|---|---|
| `accounts` | One row per account: last 4 digits, checking or credit card, nickname |
| `transactions` | Every imported transaction, exactly as Chase gave it. Amounts are negative for money out |
| `categories` | Your groups and subcategories, with `is_spending` and `tax_relevant` |
| `category_rules` | Your patterns |
| `category_overrides` | Manual fixes, by transaction fingerprint |
| `merchant_categories` | Claude's saved answers, by merchant |
| `merchant_name()` | Function: a description with the trailing `MM/DD` removed |
| `all_transactions` | View: transactions with a single `date` column and the account name |
| `transactions_categorized` | View: **the one to query.** Every transaction with its final category and where it came from |

---

## Backups

Your rules and categories are in git, but **overrides and Claude's answers live
only in the database**. Back it up now and then (adjust `18` to your Postgres
version; it'll ask for your Postgres password):

```powershell
mkdir backups -Force
& "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" -U postgres -d finances -F c -f backups\finances.dump
```

Restore into an existing database with:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" -U postgres -d finances --clean backups\finances.dump
```

`backups/` is git-ignored. It contains your financial data, so keep it private.

---

## How duplicates are avoided

Chase exports have no transaction ID, so each row gets a fingerprint (SHA-256)
built from the account, dates, description and amount. Two genuinely separate
charges that look identical (two $4.50 coffees on the same day) are told apart
by their position ("1st", "2nd"), so an overlapping download produces the same
fingerprints and nothing is lost or doubled.

**Pending transactions** (no running balance yet) are skipped, because they can
still change before posting. They load from a later download once they've posted.

The one thing that could slip through is Chase changing a posted transaction's
description afterwards, which would look like a new transaction.

---

## Troubleshooting

| You see | Fix |
|---|---|
| `relation "..." does not exist` | Run `chase-import init` |
| `violates foreign key constraint` in a rule | The subcategory isn't in `categories`. Check the spelling |
| `Could not resolve authentication method` | `ANTHROPIC_API_KEY` is missing from `.env`, or the file isn't saved |
| `SKIP ... can't tell which account` | Keep Chase's file name, or pass `--account 1234` |
| `activate` is blocked in PowerShell | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `The dashboard needs Streamlit` | `pip install -e ".[dashboard]"` |
| Dashboard: `No module named chase_import.dashboard` | Re-run `pip install -e ".[dashboard]"` |

---

## Project layout

```
chase-to-postgres/
├── src/chase_import/
│   ├── cli.py           # the chase-import command
│   ├── parser.py        # reads Chase files, skips pending, fingerprints rows
│   ├── db.py            # loads into Postgres without duplicates
│   ├── categorize.py    # asks Claude about leftover merchants
│   ├── category_list.py # reads and checks category spreadsheets
│   ├── dashboard/       # the Streamlit dashboard
│   │   ├── app.py       #   what Streamlit runs: page setup, filters, tabs
│   │   ├── data.py      #   reads from and writes to Postgres
│   │   ├── theme.py     #   colors and card styling
│   │   ├── cards.py     #   cards shared by several tabs
│   │   └── load.py, overview.py, categories.py, review.py, settings.py  # one file per tab
│   └── schema.sql       # tables, function and views (run by init and load)
├── starter_lists/       # category lists to upload in Settings (.csv)
├── seed_categories.sql  # your category list
├── seed_rules.sql       # your rules
├── tests/               # parser tests with made-up sample files
├── data/                # your Chase downloads (git-ignored)
└── .env                 # your password and API key (git-ignored)
```

## Development

```powershell
pip install -e ".[dev]"
pytest
```

The files in `tests/sample_data` are made up. Real exports belong in `data/`,
which is never committed.
