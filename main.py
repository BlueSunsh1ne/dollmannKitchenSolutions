"""
main.py
The entry point. Deliberately tiny: opens the database, makes sure the
schema is in place, and hands off to the UI.

Run with:  python3 main.py

What's NOT in here, on purpose:
  - business logic (lives in inventory.py / recipes.py / ingredients.py)
  - example data loading (lives in scripts/load_example_data.py)
  - schema migrations (a deliberate one-off script when needed)
  - AI setup (lives in ai_extract.py when that arrives)

If you find yourself adding any of the above here, it belongs elsewhere.
"""

import db


def main():
    # Open the single connection the app will use.
    conn = db.connect()
    try:
        # Idempotent: creates any missing tables/indexes, no-op otherwise.
        db.init_db(conn)

        # Hand off to the UI. Until ui.py exists, just print status and exit.
        # Swap the lines below for `import ui; ui.run(conn)` when ready.
        _print_status(conn)

    finally:
        # Always close, even if something above raised. The try/finally is
        # how we guarantee no dangling connections.
        conn.close()


def _print_status(conn):
    """Placeholder while ui.py doesn't exist yet. Confirms the wiring is
    sound by printing one-line counts per table. Delete this function once
    the real UI takes over."""
    print("Kitchen DB ready.")
    for table in ("recipes", "ingredients", "recipe_ingredients", "inventory"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<20} {count:>5} row(s)")


if __name__ == "__main__":
    main()