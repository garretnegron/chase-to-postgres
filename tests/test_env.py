"""Tests for the small helpers in chase_import.env (no database needed)."""

from chase_import.env import _version_key, looks_like_api_key, redact, save_api_key


def test_api_key_shape():
    assert looks_like_api_key("sk-ant-api03-abc")
    assert not looks_like_api_key("sk-ant-your-key-here")  # .env.example's placeholder
    assert not looks_like_api_key("hello")
    assert not looks_like_api_key("sk-ant-api03 abc")  # pasted with a space in it


def test_save_api_key_replaces_and_keeps_other_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=postgresql://x\nANTHROPIC_API_KEY=sk-ant-your-key-here\n")
    save_api_key("sk-ant-api03-new", env)
    assert env.read_text().splitlines() == [
        "DATABASE_URL=postgresql://x",
        "ANTHROPIC_API_KEY=sk-ant-api03-new",
    ]


def test_save_api_key_creates_the_file(tmp_path):
    env = tmp_path / ".env"
    save_api_key("sk-ant-api03-new", env)
    assert env.read_text() == "ANTHROPIC_API_KEY=sk-ant-api03-new\n"


def test_redact_hides_only_the_password():
    assert redact("postgresql://postgres:p%40ss@localhost:5432/finances") == (
        "postgresql://postgres:****@localhost:5432/finances")
    assert redact("postgresql://localhost:5432/finances") == "postgresql://localhost:5432/finances"


def test_newest_postgres_tools_win():
    paths = [r"C:\Program Files\PostgreSQL\9\bin\pg_dump.exe",
             r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"]
    assert max(paths, key=_version_key) == paths[1]
    mac = ["/Applications/Postgres.app/Contents/Versions/16/bin/pg_dump",
           "/Applications/Postgres.app/Contents/Versions/latest/bin/pg_dump"]
    assert max(mac, key=_version_key) == mac[1]
