"""
db.py
The foundation layer. Owns:
  - where the database file lives
  - opening a connection (with foreign keys enforced)
  - the schema, and creating the tables if they're missing

Every other module gets its connection from here. Nothing in this file
knows about ingredients, recipes, AI, or UI -- it just hands out a
correctly-configured sqlite3 connection.
"""

import sqlite3
from pathlib import Path

# Default location: kitchen.db next to wherever the app is run from.
# main.py can override this by passing a path to connect().
DEFAULT_DB_PATH = Path("kitchen.db")


# --- schema ----------------------------------------------------------------
#
# Kept here as one string so init_db can run it in a single shot.
# CREATE TABLE IF NOT EXISTS makes init_db safe to call on every startup --
# it only creates what's missing, never clobbers existing data.
#
# Notes on the design choices, in case you come back to this in 6 months:
#   - Surrogate INTEGER PRIMARY KEYs everywhere. Names get edited; ids don't.
#   - ingredients.name is UNIQUE so the vocabulary can't fragment
#     ('Eggs' twice = one row, enforced by the DB, not just by convention).
#   - recipe_ingredients uses a COMPOSITE primary key (recipe_id,
#     ingredient_id): each ingredient appears at most once per recipe.
#   - Inventory rows are batches (one row per purchase event), not
#     one-row-per-ingredient. That's why inventory has its own surrogate
#     inventory_id -- you need a stable handle on a specific batch.
#   - quantity_left tracks consumption; quantity_buy + price + buy_date
#     are preserved as purchase history even after a batch hits zero.
#     So consume() updates quantity_left to 0 -- it does NOT delete the row.
#   - Dates are stored as ISO TEXT 'YYYY-MM-DD' so they sort chronologically.
#   - ON DELETE CASCADE on recipe_ingredients: deleting a recipe cleans up
#     its ingredient links automatically.
#   - ON DELETE RESTRICT on the ingredient FKs: you can't delete an
#     ingredient that's still referenced. Forces a deliberate cleanup
#     instead of silently breaking links.

SCHEMA = """
CREATE TABLE IF NOT EXISTS recipes (
    recipe_id    INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    time_minutes INTEGER,
    effort       TEXT
);

CREATE TABLE IF NOT EXISTS ingredients (
    ingredient_id INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    min_quantity  REAL,    -- par level for "running low" alerts (optional)
    min_unit      TEXT     -- unit the min_quantity is expressed in
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_id     INTEGER NOT NULL,
    ingredient_id INTEGER NOT NULL,
    quantity      REAL,
    unit          TEXT,
    PRIMARY KEY (recipe_id, ingredient_id),
    FOREIGN KEY (recipe_id)     REFERENCES recipes(recipe_id)         ON DELETE CASCADE,
    FOREIGN KEY (ingredient_id) REFERENCES ingredients(ingredient_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS inventory (
    inventory_id   INTEGER PRIMARY KEY,
    ingredient_id  INTEGER NOT NULL,
    quantity_buy   REAL NOT NULL,    -- how much was purchased on this event
    quantity_left  REAL NOT NULL,    -- how much remains; drained by consume()
    unit           TEXT,
    location       TEXT,             -- 'fridge' / 'pantry' / 'freezer'
    buy_date       TEXT,             -- ISO 'YYYY-MM-DD'
    expiry_date    TEXT,             -- ISO 'YYYY-MM-DD'
    price          REAL,             -- total price paid for this batch
    FOREIGN KEY (ingredient_id) REFERENCES ingredients(ingredient_id) ON DELETE RESTRICT
);

-- Indexes for the queries the dashboard and consume() will run most often.
CREATE INDEX IF NOT EXISTS idx_inventory_ingredient ON inventory(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_inventory_expiry     ON inventory(expiry_date);
CREATE INDEX IF NOT EXISTS idx_recipe_ing_recipe    ON recipe_ingredients(recipe_id);
CREATE INDEX IF NOT EXISTS idx_recipe_ing_ingredient ON recipe_ingredients(ingredient_id);
"""


# --- public API ------------------------------------------------------------

def connect(db_path=DEFAULT_DB_PATH):
    """Open a connection to the database with our standard settings.

    - foreign_keys = ON: enforces the FK constraints declared above.
      MUST be set per-connection (SQLite default is OFF, for legacy reasons).
    - row_factory = sqlite3.Row: rows behave like dicts -- row['name']
      works alongside row[0]. Nicer than tuple-unpacking everywhere.

    Pass ':memory:' as db_path for a throwaway in-memory DB (useful in tests).
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    """Create any tables/indexes that don't exist yet. Safe to call on every
    startup. Does NOT migrate -- if you later change a CREATE TABLE here,
    the existing table is left untouched and you'll need a migration."""
    conn.executescript(SCHEMA)
    conn.commit()


# --- quick self-check ------------------------------------------------------
# Run `python3 db.py` to create kitchen.db and verify the tables landed.

if __name__ == "__main__":
    conn = connect()
    init_db(conn)
    tables = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )]
    print(f"Tables in {DEFAULT_DB_PATH}: {', '.join(tables)}")
    conn.close()