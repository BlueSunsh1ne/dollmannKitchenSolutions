"""get_recipes_from_ingredients(): the one function both modes share.
Deterministic SQL/Python, no AI. Never reads inventory."""

import sqlite3
from dataclasses import dataclass, field

from app.core.recipes import RecipeForMatching


@dataclass
class RecipeMatch:
    recipe_id: int
    name: str
    score: float                        # share of required ingredients you have
    have: list[str]
    missing: list[str]
    optional_have: list[str] = field(default_factory=list)
    assumed: list[str] = field(default_factory=list)      # staples
    time_minutes: int | None = None
    effort: str | None = None


def score_recipes(recipes: list[RecipeForMatching], have_ids: set[int], *,
                  staple_ids: set[int] = frozenset(), assume_staples: bool = True,
                  max_missing: int = 2) -> list[RecipeMatch]:
    """Pure scoring + ranking (fewest missing, highest score, quickest)."""
    raise NotImplementedError


def get_recipes_from_ingredients(conn: sqlite3.Connection, ingredient_ids: set[int], *,
                                 assume_staples: bool = True,
                                 max_missing: int | None = None,
                                 limit: int | None = None) -> list[RecipeMatch]:
    """Loads recipes + staples from the DB and calls score_recipes()."""
    raise NotImplementedError
