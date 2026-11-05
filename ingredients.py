"""
ingredients.py
The shared vocabulary layer. Owns the `ingredients` table.

Both inventory.py and recipes.py depend on this -- it's the only place
that resolves an ingredient name to an ingredient_id. Keeping that logic
in one file is what stops 'Eggs' and 'eggs' from drifting into two
separate rows later.

Conventions enforced here:
  - names are stored stripped + title-cased ('  eggs ' -> 'Eggs') so
    lookups are case-insensitive in practice. Tweak _normalize() if you
    prefer a different style.
  - get_or_create() is the workhorse used by other modules; outside
    callers (UI, AI extractor) should prefer it too rather than INSERTing
    into the ingredients table directly.
"""

import sqlite3


# --- internal helpers ------------------------------------------------------

def _normalize(name):
    """The canonical form of an ingredient name. Keeps the vocabulary
    consistent across however users happen to type things. Centralised
    here so every lookup and insert agrees on the rules."""
    if name is None:
        raise ValueError("ingredient name cannot be None")
    cleaned = " ".join(name.split())   # collapse internal whitespace too
    if not cleaned:
        raise ValueError("ingredient name cannot be empty")
    return cleaned.title()


# --- write side ------------------------------------------------------------

def get_or_create(conn, name):
    """Return the ingredient_id for `name`, creating the row if it's new.
    This is THE function other modules call to resolve a name to an id.

    Race-safe-ish: a UNIQUE constraint on ingredients.name means even if
    two callers tried to create the same name at once, only one row wins
    -- the second falls into the IntegrityError branch and re-selects."""
    canonical = _normalize(name)

    row = conn.execute(
        "SELECT ingredient_id FROM ingredients WHERE name = ?", (canonical,)
    ).fetchone()
    if row is not None:
        return row["ingredient_id"]

    try:
        cur = conn.execute(
            "INSERT INTO ingredients (name) VALUES (?)", (canonical,)
        )
        return cur.lastrowid
    except sqlite3.IntegrityError:
        # someone else inserted the same name between our SELECT and INSERT;
        # re-select to find their id.
        row = conn.execute(
            "SELECT ingredient_id FROM ingredients WHERE name = ?", (canonical,)
        ).fetchone()
        return row["ingredient_id"]


def rename(conn, ingredient_id, new_name):
    """Rename an existing ingredient. Useful when reviewing the AI's
    proposed list and fixing a label. Raises if the new name collides
    with another existing ingredient -- because that's a MERGE, not a
    rename, and merging needs its own deliberate function."""
    canonical = _normalize(new_name)
    try:
        conn.execute(
            "UPDATE ingredients SET name = ? WHERE ingredient_id = ?",
            (canonical, ingredient_id),
        )
    except sqlite3.IntegrityError:
        raise ValueError(
            f"'{canonical}' already exists as another ingredient. "
            "Use merge() instead if you meant to combine them."
        )


def set_par_level(conn, ingredient_id, min_quantity, min_unit):
    """Set the 'running low' threshold for an ingredient.

    e.g. set_par_level(conn, eggs_id, 4, 'whole') means: warn me when
    total eggs in inventory drops below 4 whole. Used later by the
    dashboard's 'running low' band."""
    conn.execute(
        "UPDATE ingredients SET min_quantity = ?, min_unit = ? "
        "WHERE ingredient_id = ?",
        (min_quantity, min_unit, ingredient_id),
    )


# --- read side -------------------------------------------------------------

def get_by_id(conn, ingredient_id):
    """Fetch one ingredient row, or None."""
    return conn.execute(
        "SELECT ingredient_id, name, min_quantity, min_unit "
        "FROM ingredients WHERE ingredient_id = ?",
        (ingredient_id,),
    ).fetchone()


def get_by_name(conn, name):
    """Fetch one ingredient row by name (normalized), or None.
    Does NOT create -- use get_or_create() for that."""
    return conn.execute(
        "SELECT ingredient_id, name, min_quantity, min_unit "
        "FROM ingredients WHERE name = ?",
        (_normalize(name),),
    ).fetchone()


def list_all(conn):
    """Return every ingredient, alphabetically. Handy for the AI extractor
    to receive as the 'known vocabulary' it should match against, and for
    a dropdown in manual entry."""
    return conn.execute(
        "SELECT ingredient_id, name, min_quantity, min_unit "
        "FROM ingredients ORDER BY name"
    ).fetchall()


# --- quick self-check ------------------------------------------------------

if __name__ == "__main__":
    import db

    # use an in-memory db so this script doesn't muddy kitchen.db
    conn = db.connect(":memory:")
    db.init_db(conn)

    # get_or_create is idempotent and case/whitespace-insensitive
    a = get_or_create(conn, "Eggs")
    b = get_or_create(conn, "  eggs  ")
    c = get_or_create(conn, "EGGS")
    assert a == b == c, "normalization failed"

    # rename works
    butter_id = get_or_create(conn, "buter")   # typo
    rename(conn, butter_id, "Butter")

    # rename collision is refused
    get_or_create(conn, "Salt")
    try:
        rename(conn, butter_id, "salt")        # would collide with 'Salt'
        print("FAIL: collision should have been refused")
    except ValueError as e:
        pass   # expected

    # par level
    eggs_id = get_or_create(conn, "Eggs")
    set_par_level(conn, eggs_id, 4, "whole")

    print(f"{'id':>3}  {'name':<10} {'min_qty':>8} {'min_unit':<8}")
    for row in list_all(conn):
        mq = row["min_quantity"] if row["min_quantity"] is not None else ""
        mu = row["min_unit"]     if row["min_unit"]     is not None else ""
        print(f"{row['ingredient_id']:>3}  {row['name']:<10} {str(mq):>8} {mu:<8}")
    conn.close()