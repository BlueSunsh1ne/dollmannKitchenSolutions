"""Speech-to-text result -> list of ingredients the user confirms.

  text -> interpret() -> [Proposal] -> user edits/confirms -> confirm() -> IDs
"""

import sqlite3
from dataclasses import dataclass

from app.ai.client import AIClient


@dataclass
class Proposal:
    said: str                      # what the user said, e.g. 'Hähnchen'
    ingredient_id: int | None      # known ingredient, or None if new
    name: str                      # canonical name, or proposed new name
    is_new: bool                   # True = would be added on confirm


def interpret(conn: sqlite3.Connection, text: str, *,
              client: AIClient | None = None) -> list[Proposal]:
    """Ask the LLM to map free text onto the vocabulary. Validates every
    returned id against the DB. Writes nothing."""
    raise NotImplementedError


def confirm(conn: sqlite3.Connection, proposals: list[Proposal]) -> set[int]:
    """Store confirmed new ingredients, return all ingredient IDs. No commit."""
    raise NotImplementedError
