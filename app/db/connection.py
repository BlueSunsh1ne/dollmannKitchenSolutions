"""Hands out configured SQLite connections and creates the schema."""

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a connection: foreign keys on, WAL mode, rows as sqlite3.Row."""
    raise NotImplementedError


def init_db(conn: sqlite3.Connection) -> None:
    """Run schema.sql; refuse databases with an unknown schema version."""
    raise NotImplementedError


def open_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    """connect() + init_db(). What scripts and the API use."""
    raise NotImplementedError
