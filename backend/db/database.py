"""SQLite connection and repeatable schema bootstrap."""

from pathlib import Path
import sqlite3

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(path: str | Path) -> None:
    with connect(path) as connection:
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        columns = {row[1] for row in connection.execute("PRAGMA table_info(incidents)")}
        if "ingested_at" not in columns:
            # Legacy ingestion time is unknown; do not infer it from another timestamp.
            connection.execute("ALTER TABLE incidents ADD COLUMN ingested_at TEXT")
