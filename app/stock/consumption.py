"""LATER (committed mode): cooking drains the stock."""

import sqlite3
from dataclasses import dataclass, field


@dataclass
class ConsumptionReport:
    drained: dict[int, float] = field(default_factory=dict)   # id -> amount
    now_empty: list[str] = field(default_factory=list)


def log_meal(conn: sqlite3.Connection, recipe_id: int, *,
             corrections: dict[int, float] | None = None) -> ConsumptionReport:
    """Deduct a cooked recipe (plus corrections) from stock. No commit."""
    raise NotImplementedError
