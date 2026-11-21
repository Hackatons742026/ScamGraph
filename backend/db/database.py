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
