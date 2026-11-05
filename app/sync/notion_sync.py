"""Notion -> SQLite. Notion is the source of truth for recipes."""

import sqlite3
from dataclasses import dataclass, field

from app.ai.client import AIClient
from app.sync.notion_client import NotionClient


@dataclass
class SyncReport:
    created: int = 0
    updated: int = 0
    deleted: int = 0
    new_ingredients: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def sync_recipes(conn: sqlite3.Connection, *, notion: NotionClient | None = None,
                 ai: AIClient | None = None, full: bool = False) -> SyncReport:
    """Incremental by default; full=True also removes deleted recipes."""
    raise NotImplementedError
