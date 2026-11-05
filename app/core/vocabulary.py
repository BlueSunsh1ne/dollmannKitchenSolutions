"""The ingredient list. Plain lookups only: understanding what the user
meant is the LLM's job (app/ai/interpret.py), not this module's."""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Ingredient:
    ingredient_id: int
    name: str
    category: str | None
    default_unit: str | None
    is_staple: bool


def add_ingredient(conn: sqlite3.Connection, name: str, *,
                   ingredient_id: int | None = None, category: str | None = None,
                   container: str | None = None, default_unit: str | None = None,
                   is_staple: bool = False) -> int:
    """Insert (or update by id) one ingredient. Returns its id. No commit."""
    raise NotImplementedError


def get_by_id(conn: sqlite3.Connection, ingredient_id: int) -> Ingredient | None:
    """One ingredient by id, or None."""
    raise NotImplementedError


def get_by_name(conn: sqlite3.Connection, name: str) -> Ingredient | None:
    """One ingredient by exact name (case-insensitive), or None."""
    raise NotImplementedError


def list_all(conn: sqlite3.Connection) -> list[Ingredient]:
    """Every ingredient. This list is what the LLM gets as context."""
    raise NotImplementedError


def staple_ids(conn: sqlite3.Connection) -> set[int]:
    """IDs the matcher assumes are always in the kitchen (salt, oil, ...)."""
    raise NotImplementedError


def rename(conn: sqlite3.Connection, ingredient_id: int, new_name: str) -> None:
    """Rename; refuses if the name is taken by another ingredient. No commit."""
    raise NotImplementedError


def set_staple(conn: sqlite3.Connection, ingredient_id: int, is_staple: bool = True) -> None:
    """Mark or unmark an ingredient as staple. No commit."""
    raise NotImplementedError
