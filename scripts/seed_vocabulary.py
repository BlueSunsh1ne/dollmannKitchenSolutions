"""Load datasets/ingredient_id_list.xlsx (+ data/staples.txt) into the DB.

    python -m scripts.seed_vocabulary [--xlsx PATH] [--db PATH]
"""

import sqlite3
from pathlib import Path


def read_sheet(path: Path) -> list[dict]:
    """Rows of the sheet as dicts (id, name, container, unit, category)."""
    raise NotImplementedError


def seed(conn: sqlite3.Connection, xlsx_path: Path) -> list[str]:
    """Upsert all ingredients by id, mark staples. Returns warnings."""
    raise NotImplementedError


def main(argv: list[str] | None = None) -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
