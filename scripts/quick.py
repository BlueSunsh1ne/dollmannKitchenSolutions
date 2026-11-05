"""Quick mode in the terminal (stands in for the phone until the API exists).

    text -> interpret() -> show proposals -> user confirms -> confirm()
         -> get_recipes_from_ingredients() -> print
"""

import sqlite3
from typing import Callable


def run_once(conn: sqlite3.Connection, text: str, *,
             ask: Callable[[str], str] = input,
             out: Callable[[str], None] = print) -> None:
    """One full round, including the confirm prompt."""
    raise NotImplementedError


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
