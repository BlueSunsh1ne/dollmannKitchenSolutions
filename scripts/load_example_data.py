"""
scripts/load_example_data.py

One-off seeder. Loads the data from your screenshot into kitchen.db so
you have something real to look at in DB Browser. Run by hand, NOT from
main.py:

    python3 scripts/load_example_data.py

What this does that main.py deliberately doesn't:
  - Wipes any existing seed data first (so re-running is safe and
    idempotent, unlike just calling add_inventory repeatedly).
  - Inserts the two recipes from the screenshot.
  - Inserts the seven inventory batches from the screenshot.
  - Sets a couple of par levels so 'running low' has something to show.

If you've put real data into kitchen.db already, DON'T run this -- it
will clear the inventory and replace recipes by name. There's a guard
at the top that refuses to run unless --force is passed once it sees
non-trivial existing data.
"""

import sys
from pathlib import Path

# Make the parent directory importable so we can `import db` etc. from a
# script that lives in scripts/. This is the standard trick for one-off
# tools that sit alongside the app rather than inside it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import ingredients
import inventory
import recipes


def _confirm_safe_to_run(conn, force):
    """Refuse to clobber a database that looks like it has real data,
    unless the user explicitly passes --force."""
    inv_rows = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
    rec_rows = conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    if (inv_rows or rec_rows) and not force:
        print(
            f"Refusing to run: kitchen.db already has "
            f"{inv_rows} inventory + {rec_rows} recipe rows.\n"
            f"Pass --force if you really mean to reseed."
        )
        sys.exit(1)


def main():
    force = "--force" in sys.argv

    conn = db.connect()
    db.init_db(conn)
    _confirm_safe_to_run(conn, force)

    # Clean slate for the inventory. (Recipes are replaced by name in
    # add_recipe, so we don't need to clear them manually.)
    inventory.clear_inventory(conn)

    # --- recipes from the screenshot ---------------------------------------
    recipes.add_recipe(conn, "Sunny side eggs with beans and toast", 15, "low", [
        ("Eggs",   2,   "whole"),
        ("Butter", 10,  "g"),
        ("Beans",  400, "g"),
        ("Toast",  2,   "slice"),
        ("Salt",   1,   "pinch"),
        ("Pepper", 1,   "pinch"),
    ])
    recipes.add_recipe(conn, "Chicken wrap", 20, "middle", [
        ("Chicken", 300, "g"),
        ("Wraps",   1,   "whole"),
    ])

    # --- inventory batches from the screenshot ----------------------------
    # (ingredient, qty_buy, unit, location, buy_date, expiry_date, price)
    inventory.add_inventory(conn, "Eggs",   10,  "whole", "fridge", "2026-06-01", "2026-07-24", 3.0)
    inventory.add_inventory(conn, "Butter", 250, "g",     "fridge", "2026-06-01", "2026-08-01")
    inventory.add_inventory(conn, "Beans",  460, "g",     "pantry", "2026-06-01", "2026-10-01")
    inventory.add_inventory(conn, "Toast",  24,  "slice", "pantry", "2026-06-01", "2026-07-07")
    inventory.add_inventory(conn, "Salt",   100, "pinch", "pantry", "2026-06-01", "2027-01-01")
    inventory.add_inventory(conn, "Pepper", 100, "pinch", "pantry", "2026-06-01", "2027-01-01")
    inventory.add_inventory(conn, "Eggs",   10,  "whole", "fridge", "2026-06-10", "2026-09-01", 4.0)

    # Mirror the screenshot's "quantity_left" by consuming the difference
    # from quantity_buy.
    inventory.consume(conn, [
        ("Eggs",   7,  "whole"),    # 10 + 10 - 7 = 13 left (3 + 10 split)
        ("Butter", 50, "g"),        # 250 - 50 = 200
        ("Toast",  9,  "slice"),    # 24 - 9 = 15
        ("Pepper", 40, "pinch"),    # 100 - 40 = 60
        ("Salt",   100, "pinch"),   # drain to 0 (history row remains)
    ])

    # --- par levels (gives 'running low' something to surface) ------------
    eggs_id   = ingredients.get_by_name(conn, "Eggs")["ingredient_id"]
    butter_id = ingredients.get_by_name(conn, "Butter")["ingredient_id"]
    salt_id   = ingredients.get_by_name(conn, "Salt")["ingredient_id"]
    ingredients.set_par_level(conn, eggs_id,   6,   "whole")  # 13 -- OK
    ingredients.set_par_level(conn, butter_id, 300, "g")      # 200 -- LOW
    ingredients.set_par_level(conn, salt_id,   50,  "pinch")  # 0   -- LOW

    conn.commit()

    # --- summary so you can sanity-check before opening DB Browser --------
    print("Seed complete. Snapshot:")
    print(f"  recipes      : {conn.execute('SELECT COUNT(*) FROM recipes').fetchone()[0]}")
    print(f"  ingredients  : {conn.execute('SELECT COUNT(*) FROM ingredients').fetchone()[0]}")
    print(f"  inventory    : {conn.execute('SELECT COUNT(*) FROM inventory').fetchone()[0]} "
          "(includes zero-quantity history rows)")
    conn.close()


if __name__ == "__main__":
    main()