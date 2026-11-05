"""LATER (committed mode): what's in the kitchen."""

import sqlite3


def add_purchase(conn: sqlite3.Connection, ingredient_id: int, quantity: float,
                 unit: str | None, *, buy_date: str | None = None,
                 expiry_date: str | None = None, price: float | None = None,
                 location: str | None = None) -> int:
    """One purchase batch. Returns inventory_id. No commit."""
    raise NotImplementedError


def current_stock_ids(conn: sqlite3.Connection) -> set[int]:
    """Ingredient IDs with anything left. Feeds the matcher."""
    raise NotImplementedError
