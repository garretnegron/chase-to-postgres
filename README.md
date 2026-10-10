# chase-to-postgres

Load Chase checking and credit card exports (CSV, Excel or Parquet) into a
Postgres database. Re-importing a file, or a download that overlaps an earlier
one, never creates duplicates.

```
> chase-import load downloads
LOAD  Chase1234_Activity_20261004.CSV: 4 new, 0 already in the database (checking ...1234)
LOAD  Chase1234_Activity_20261009.CSV: 2 new, 2 already in the database (checking ...1234)
LOAD  Chase5678_Activity20260901_20260930_20261009.CSV: 5 new, 0 already in the database (credit_card ...5678)
Done. 11 new transactions.
```

## One-time setup (Windows)

1. **Install Postgres** from <https://www.postgresql.org/download/windows/>
   (the EDB installer). Remember the password you give the `postgres` user.
   Then open **SQL Shell (psql)** from the Start menu, press Enter through the
   prompts, type that password, and run:

   ```sql
   CREATE DATABASE finances;
   ```

2. **Get the code and install it** (PowerShell, or PyCharm's terminal):

   ```powershell
   git clone https://github.com/YOUR_USERNAME/chase-to-postgres.git
   cd chase-to-postgres
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e .
   ```

   If PowerShell refuses to run `activate`, run this once and try again:
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

3. **Point it at your database.** Copy `.env.example` to `.env` and put your
   Postgres password in it:

   ```
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/finances
   ```

   `.env` is in `.gitignore`, so the password never goes to GitHub.

4. **Create the tables:** `chase-import init`

## Each time you want to import

1. On chase.com, open an account, click the **download** icon above the
   transactions, pick **Spreadsheet (Excel, CSV)** and a date range. Overlap
   with the last download is fine.
2. Put the files in a `data` folder inside the project (also git-ignored) and run:

   ```powershell
   .venv\Scripts\activate
   chase-import load data
   ```

Other commands:

| Command | What it does |
|---|---|
| `chase-import load data --dry-run` | Check the files without touching the database |
| `chase-import load file.csv --account 1234` | If the file name doesn't contain `Chase1234`, say which account it is |
| `chase-import load data --name "Dad checking"` | Give the account a friendly name (sticks for later imports) |
| `chase-import summary` | Count and date range per account |

Keep Chase's original file names (`Chase1234_Activity_...`). That's how the
importer knows which account a file belongs to.

## What ends up in the database

- `accounts`: one row per card/account (last 4 digits, checking or credit card, nickname)
- `transactions`: every column Chase exports. Amounts are negative for money out,
  positive for money in (deposits, card payments, refunds).
- `all_transactions` view: everything in one place with a single `date` column,
  the easiest thing to query:

```sql
-- Spending by month and Chase category (credit cards)
SELECT date_trunc('month', date)::date AS month, category, sum(-amount) AS spent
FROM all_transactions
WHERE account_kind = 'credit_card' AND amount < 0
GROUP BY 1, 2
ORDER BY 1, 3 DESC;
```

## How duplicates are avoided

Chase exports have no transaction ID, so each row gets a fingerprint built from
the account, dates, description and amount. Two genuinely separate charges that
look identical (two $4.50 coffees on the same day) are told apart by their
position ("1st", "2nd"), so an overlapping download produces the same two
fingerprints and neither coffee is lost or doubled.

One edge case: if a later download adds a third identical charge on a day
you've already imported, it's still picked up as the 3rd. The only thing that
could slip through is Chase changing a description after the fact, which
would look like a new transaction.

## Development

```
pip install -e .[dev]
pytest
```

The files in `tests/sample_data` are made up. Real exports belong in `data/`,
which is never committed.
