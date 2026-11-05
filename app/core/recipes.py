"""The recipe store. Lines arrive already resolved to ingredient IDs
(by interpret() during the Notion sync)."""

import sqlite3
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RecipeLine:
    ingredient_id: int
    quantity: float | None = None
    unit: str | None = None
    optional: bool = False
    raw_text: str | None = None       # original line, e.g. '300 g chicken'


@dataclass
class RecipeForMatching:
    """Slim shape the matcher needs: IDs only, no quantities."""
    recipe_id: int
    name: str
    time_minutes: int | None
    effort: str | None
    required: dict[int, str] = field(default_factory=dict)    # id -> name
    optional: dict[int, str] = field(default_factory=dict)


def save_recipe(conn: sqlite3.Connection, name: str, lines: list[RecipeLine], *,
                time_minutes: int | None = None, effort: str | None = None,
                servings: int | None = None, notion_page_id: str | None = None,
                notion_last_edited: str | None = None) -> int:
    """Create or replace a recipe (identity: notion_page_id, else name).
    Returns recipe_id. No commit."""
    raise NotImplementedError


def delete_recipe(conn: sqlite3.Connection, recipe_id: int) -> bool:
    """Remove a recipe; its lines cascade. No commit."""
    raise NotImplementedError


def get_recipe(conn: sqlite3.Connection, recipe_id: int) -> dict | None:
    """One recipe with its full ingredient list, or None."""
    raise NotImplementedError


def list_recipes(conn: sqlite3.Connection) -> list[dict]:
    """All recipes, metadata only."""
    raise NotImplementedError


def load_for_matching(conn: sqlite3.Connection) -> list[RecipeForMatching]:
    """Every recipe with its ingredient IDs, in one query."""
    raise NotImplementedError
