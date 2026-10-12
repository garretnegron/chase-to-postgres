# 🏦 chase-to-postgres

Turn your Chase bank and credit card downloads into a clean, categorized Postgres
database you own and can query however you like.

![The spending dashboard: headline totals and spending by month, stacked by category](assets/dashboard.png)

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

- **Windows or Mac.** Windows steps are first; Mac users, see [Setup on a Mac](#setup-on-a-mac)
- **Python 3.10+**
- **PostgreSQL 15 or newer.** The rules table uses a feature added in 15
- **An Anthropic API key**, only for `categorize`. Everything else works without one

---

## One-time setup

**The quick way (Windows):** install Python and PostgreSQL (steps 1 and 2 below
describe the installers), get the code, then in PowerShell, in the project folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
```

It asks for the postgres password once, then creates the database, installs the
app, writes `.env`, creates the tables, puts the icon on the desktop and runs
`chase-import doctor`. Safe to run again. **On a Mac,** see
[Setup on a Mac](#setup-on-a-mac).

The steps below are what the script does, one at a time.

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

(Or skip this step and upload a category list from the dashboard's welcome
page instead: see `starter_lists/`.)

### 6. Put an icon on the desktop

```powershell
chase-import shortcut
```

This adds a **Spending Dashboard** icon to the desktop. Double-click it to open
the dashboard: no terminal, no typing. A small black window opens minimized in
the taskbar; that window *is* the dashboard, so closing it stops it.
Double-clicking again while it's running just brings the dashboard back up.

### 7. Check everything

```powershell
chase-import doctor
```

Checks Python, the packages, `.env`, the database connection, the API key, the
backup tool and the desktop icon, and says how to fix anything marked `[FAIL]`.
Run it any time something seems off.

---

## Setup on a Mac

1. **Install Python** from <https://www.python.org/downloads/macos/>. The Mac
   doesn't come with a usable one.
2. **Install Postgres.app** from <https://postgresapp.com>: drag it into
   Applications, open it, and click **Initialize**. An elephant 🐘 appears in the
   menu bar while it's running.
3. **Get the code.** Either download it (the green **Code** button on GitHub →
   **Download ZIP**, then double-click the ZIP to unzip it), or, to be able to
   update with `git pull` later, clone it in Terminal:
   `git clone https://github.com/garretnegron/chase-to-postgres.git`
   (the first `git` asks to install Apple's command line tools: click **Install**).
4. **Run the setup script.** Open **Terminal** (Applications → Utilities), type
   `bash ` (with a space), drag **setup_mac.sh** from the project folder into the
   Terminal window, and press Return. It:
   - checks for Python and Postgres, with a clear message if one is missing
   - creates the `finances` database
   - installs the app into `.venv`
   - writes the settings file, `.env`
   - creates the tables
   - puts **Spending Dashboard** on the Desktop
   - finishes with `chase-import doctor`
5. **Double-click Spending Dashboard** on the Desktop. A Terminal window opens
   along with the dashboard; closing that window stops it. The welcome page walks
   you through the rest, including pasting your Claude API key.

> **"Terminal would like to connect" / "Python would like to connect":** recent
> versions of Postgres.app ask once for each program that connects. Click **OK**
> both times.

The script is safe to run again any time: each step skips what's already done.
If you move the project folder, run it again to point the desktop launcher at
the new place.

`.env` starts with a dot, so Finder hides it. Press **Cmd + Shift + .** in Finder
to show hidden files.

**If you downloaded the ZIP:** to update later, download the new ZIP and copy
your `.env`, `backups/` and `data/` folders into the new folder before deleting
the old one: they're the only things that are yours.

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
| `chase-import shortcut` | Put a **Spending Dashboard** launcher on the desktop (Windows or Mac) |
| `chase-import backup` | Save a backup of the database into `backups/` |
| `chase-import doctor` | Check the whole setup and say how to fix problems |

---

## Dashboard

Double-click the **Spending Dashboard** icon (see setup step 6), or run:

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
| **Overview** | Spent, average per month, income, and the difference; spending by month stacked by group; your top merchants |
| **Categories** | Pick one group (say, Food & Drink) to see its subcategories month by month and its top merchants |
| **Review** | A table of transactions you can re-categorize from a dropdown. Filter by who decided (AI, rule, by hand, uncategorized) or search a merchant, change subcategories, then press **Save** |
| **Settings** | Your category list: edit it in a table, import or export it as a spreadsheet, add one, or remove one (you choose where its transactions go) |

Good to know:

- Only **spending** counts in the totals and charts: subcategories with
  `is_spending = false` (income, transfers, card payments) are left out.
- **Income** counts only subcategories marked **Is income** (paychecks, say).
  Card payments and transfers between your own accounts aren't income: paying
  a card shows up as money *out* of checking and money *in* to the card.
- Each group keeps the same color everywhere. The 7 biggest get their own color,
  and the rest are combined into gray **All other**.
- Fixes saved on the **Review** tab are overrides (see below), so they outrank rules
  and AI and survive reloads.
- The dashboard only uses the columns and flags in `transactions_categorized`, never
  specific category names, so it works with anyone's category list.
- Loading on the Import tab and saving on Review or Settings refresh everything
  right away. After loading from the terminal instead, give it up to a minute.

---

## Managing categories

### Categories

**The easy way:** the dashboard's **Settings** tab. To start from a ready-made
list, upload one of the files in `starter_lists/` (or download the blank template
and fill it in). Uploading adds new subcategories and updates changed ones; it
never removes anything.

| Group | Subcategory | Counts as spending | Is income | Tax-relevant |
|---|---|---|---|---|
| Food & Drink | Groceries | yes | no | no |
| Income | Paycheck | no | yes | no |

The yes/no columns are optional. Left blank, a subcategory you already have
keeps its setting.

**The SQL way:** `seed_categories.sql`, below. Once you manage categories in the
dashboard, the database is the real list and the seed files are just a starting
point for new installs.

#### `seed_categories.sql`

Two levels: a **group** (`Food & Drink`) and a **subcategory** (`Restaurants`).
Each subcategory also has three flags:

- `is_spending`: `false` for Income and Money Movement (transfers, card payments),
  so they don't inflate your spending totals
- `is_income`: `true` for money you earn (paychecks). This is what the dashboard's
  **Income** adds up; transfers and card payments stay out of it
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
| `categories` | Your groups and subcategories, with `is_spending`, `is_income` and `tax_relevant` |
| `category_rules` | Your patterns |
| `category_overrides` | Manual fixes, by transaction fingerprint |
| `merchant_categories` | Claude's saved answers, by merchant |
| `merchant_name()` | Function: a description with the trailing `MM/DD` removed |
| `all_transactions` | View: transactions with a single `date` column and the account name |
| `transactions_categorized` | View: **the one to query.** Every transaction with its final category and where it came from |

---

## Backups

Your categories, manual fixes and Claude's answers live **only in the database**.
Back it up now and then, and before big changes: press **Back up now** on the
dashboard's **Settings** tab, or run

```powershell
chase-import backup
```

Either way you get a file like `backups/finances-2026-10-12-143000.dump`. It finds
Postgres's `pg_dump` by itself (Windows, Postgres.app or Homebrew). Copy the
`backups` folder somewhere else once in a while (a USB stick, a cloud drive): a
backup on the same laptop won't survive the laptop.

Restore into an existing database with (adjust `18` to your Postgres version and
the file name to your backup):

```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" -U postgres -d finances --clean backups\finances-2026-10-12-143000.dump
```

On a Mac with Postgres.app: `pg_restore -d finances --clean backups/finances-2026-10-12-143000.dump`

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
| Anything else | Run `chase-import doctor` and fix what it marks `[FAIL]` |

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
│   ├── env.py           # where things live; API key, pg_dump finder
│   ├── backup.py        # backups with pg_dump
│   ├── dashboard/       # the Streamlit dashboard
│   │   ├── app.py       #   what Streamlit runs: page setup, filters, tabs
│   │   ├── data.py      #   reads from and writes to Postgres
│   │   ├── theme.py     #   colors and card styling
│   │   ├── cards.py     #   cards shared by several tabs
│   │   ├── welcome.py, apikey.py, notify.py  #   first-run page, key box, pop-ups
│   │   └── load.py, overview.py, categories.py, review.py, settings.py  # one file per tab
│   └── schema.sql       # tables, function and views (run by init and load)
├── starter_lists/       # category lists to upload in Settings (.csv)
├── Spending Dashboard.bat  # double-click to open the dashboard (the desktop icon runs it)
├── setup_mac.sh         # one-command setup on a Mac
├── setup_windows.ps1    # one-command setup on Windows
├── assets/              # the desktop icon and the README screenshot
├── seed_categories.sql  # your category list
├── seed_rules.sql       # your rules
├── tests/               # tests, with made-up sample files
├── .github/workflows/   # the install-and-test run on GitHub's Mac and Linux machines
├── data/                # your Chase downloads (git-ignored)
└── .env                 # your password and API key (git-ignored)
```

## Development

```powershell
pip install -e ".[dev,dashboard]"
pytest
```

The files in `tests/sample_data` are made up. Real exports belong in `data/`,
which is never committed.

**Tested on a fresh Mac and Linux machine:** `.github/workflows/test.yml` tells
GitHub to install everything from scratch (Postgres, Python, the app), run the
tests (including the whole dashboard against a scratch database), load the sample
files, run `doctor`, make a backup, and start the dashboard the way the desktop
launcher does. It runs on every push to `main` and every pull request; the result
is the ✅ or ❌ next to each commit, and the details are on the **Actions** tab.
`test_dashboard_smoke.py` only runs when `CHASE_TEST_DATABASE_URL` is set, so it
never touches your real database.
