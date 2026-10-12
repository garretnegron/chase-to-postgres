# One-time setup on Windows. In PowerShell, from this folder, run:
#
#     powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
#
# Before running it, install Python (python.org, tick "Add python.exe to PATH")
# and PostgreSQL (the EDB installer), and remember the postgres password you chose.
#
# It's safe to run again: each step skips what's already done.

# "Continue": programs like psql and pip print warnings to the error channel, which
# "Stop" would treat as a crash. Each step checks $LASTEXITCODE itself instead.
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot   # always work in the project folder

$DbName = "finances"

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "    $text" }
function Fail($text) { Write-Host "`n[FAIL] $text`n" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- 1. Python
Step "Looking for Python 3.10 or newer"
$Python = $null
foreach ($candidate in @("py -3", "python")) {
    $exe, $arg = $candidate -split " ", 2
    if (Get-Command $exe -ErrorAction SilentlyContinue) {
        $args_ = @(); if ($arg) { $args_ += $arg }
        & $exe @args_ -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $Python = @($exe) + $args_; break }
    }
}
if (-not $Python) { Fail "No Python 3.10 or newer found. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') and run this again." }
$PyExe = $Python[0]; $PyArgs = @($Python | Select-Object -Skip 1)
Ok ("Found " + (& $PyExe @PyArgs --version))

# ---------------------------------------------------------------- 2. PostgreSQL
Step "Looking for PostgreSQL"
$psql = Get-Command psql -ErrorAction SilentlyContinue
if ($psql) {
    $PgBin = Split-Path $psql.Source
} else {
    # The installer doesn't add its tools to the PATH: use the newest version installed
    $PgBin = Get-ChildItem "$env:ProgramFiles\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue |
        Sort-Object { [int]($_.Directory.Parent.Name -replace '\D', '') } |
        Select-Object -Last 1 | ForEach-Object { $_.DirectoryName }
}
if (-not $PgBin) { Fail "PostgreSQL isn't installed. Install it from https://www.postgresql.org/download/windows/ and run this again." }
$env:PATH = "$PgBin;$env:PATH"
Ok ("Found " + (& psql --version))

& pg_isready -h localhost -p 5432 -q
if ($LASTEXITCODE -ne 0) { Fail "PostgreSQL isn't running. Press the Windows key, type Services, find postgresql-x64-..., right-click it and choose Start. Then run this again." }
Ok "PostgreSQL is running"

# ---------------------------------------------------------------- 3. settings + database
if (Test-Path .env) {
    Step "Settings file (.env) already exists"
    Ok "Left as it is. Using its DATABASE_URL."
} else {
    Step "Creating the '$DbName' database"
    $secure = Read-Host -AsSecureString "    The postgres password you chose when installing PostgreSQL"
    $password = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    $env:PGPASSWORD = $password   # psql and createdb read the password from here

    $exists = & psql -U postgres -h localhost -tAc "SELECT 1 FROM pg_database WHERE datname = '$DbName'" postgres 2>&1
    if ($LASTEXITCODE -ne 0) { Fail "Couldn't log in to PostgreSQL: $exists`n       Is the password right?" }
    if ($exists -match "1") {
        Ok "Already there"
    } else {
        & createdb -U postgres -h localhost $DbName
        if ($LASTEXITCODE -ne 0) { Fail "Couldn't create the database." }
        Ok "Created"
    }

    Step "Writing the settings file (.env)"
    # Characters like @ or : in a password must be escaped inside a URL
    $encoded = [Uri]::EscapeDataString($password)
    @(
        "# Settings for chase-to-postgres. Made by setup_windows.ps1; never committed to git."
        "DATABASE_URL=postgresql://postgres:$encoded@localhost:5432/$DbName"
        "# The Claude API key gets added here when you paste it into the dashboard."
    ) | Set-Content -Path .env -Encoding ascii
    Ok "Created .env"
    Remove-Item Env:PGPASSWORD
}

# ---------------------------------------------------------------- 4. the app
Step "Installing the app (this takes a minute or two the first time)"
if (-not (Test-Path .venv\Scripts\python.exe)) {
    & $PyExe @PyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { Fail "Couldn't create .venv." }
}
& .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .venv\Scripts\python.exe -m pip install --quiet -e ".[dashboard]"
if ($LASTEXITCODE -ne 0) { Fail "Installing the app failed: see the messages above." }
Ok "Installed"

# ---------------------------------------------------------------- 5. tables + launcher
Step "Creating the tables"
& .venv\Scripts\chase-import.exe init
if ($LASTEXITCODE -ne 0) { Fail "Couldn't create the tables: see the message above." }

Step "Putting Spending Dashboard on the desktop"
& .venv\Scripts\chase-import.exe shortcut

# ---------------------------------------------------------------- 6. check
Step "Checking everything"
& .venv\Scripts\chase-import.exe doctor

Write-Host "`nAll set! Double-click 'Spending Dashboard' on your desktop to open it." -ForegroundColor Green
Write-Host "The welcome page walks you through the rest.`n"
