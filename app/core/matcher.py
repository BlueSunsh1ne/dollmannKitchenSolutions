"""get_recipes_from_ingredients(): the one function both modes share.
Deterministic SQL/Python, no AI. Never reads inventory."""

import sqlite3
from dataclasses import dataclass, field

from app.core.recipes import RecipeForMatching


@dataclass
class RecipeMatch:
    recipe_id: int
    name: str
    score: float                        # share of REQUIRED ingredients you have
    have: list[str]
    missing: list[str]
    optional_have: list[str] = field(default_factory=list)
    optional_missing: list[str] = field(default_factory=list)  # 'for the complete recipe'
    time_minutes: int | None = None
    effort: str | None = None


def score_recipes(recipes: list[RecipeForMatching], have_ids: set[int], *,
                  max_missing: int = 2) -> list[RecipeMatch]:
    """Pure scoring + ranking (fewest missing, highest score, quickest).
    Optional ingredients never count as missing; they are listed in
    optional_missing so the user knows what completes the recipe."""
    raise NotImplementedError


def get_recipes_from_ingredients(conn: sqlite3.Connection, ingredient_ids: set[int], *,
                                 max_missing: int | None = None,
                                 limit: int | None = None) -> list[RecipeMatch]:
    """Loads recipes from the DB and calls score_recipes()."""
    raise NotImplementedError
