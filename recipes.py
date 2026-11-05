"""
recipes.py
The recipe layer. Owns the `recipes` and `recipe_ingredients` tables, and
the headline query that joins them to inventory: get_makeable_recipes().

For now, recipes are entered manually -- no AI here. The AI layer reads
receipts to populate INVENTORY; recipes are curated by hand.

Writes:
  add_recipe()    -- create OR replace a recipe + its ingredient list
  delete_recipe() -- remove a recipe (its ingredient links cascade)

Reads:
  get_recipe()              -- one recipe with its full ingredient list
  list_recipes()            -- all recipes, metadata only (for browsing)
  get_makeable_recipes()    -- strict yes/no: every ingredient available
"""

import ingredients

# Match inventory.py's tolerance so "this is empty" means the same thing
# across modules.
_EPS = 1e-9


# --- writes ----------------------------------------------------------------

def add_recipe(conn, name, time_minutes, effort, items):
    """Create OR replace a recipe (REPLACE on duplicate name -- the old
    recipe and its ingredient links are removed first, then the new one
    is inserted). The ON DELETE CASCADE on recipe_ingredients handles the
    link cleanup automatically.

    items: list of (ingredient_name, quantity, unit) tuples. May be empty
    if you're stubbing out a recipe to fill in later -- but an empty-items
    recipe is treated as 'not makeable' by get_makeable_recipes().

    Auto-creates any new ingredients via ingredients.get_or_create.
    Returns the new recipe_id. Does NOT commit.
    """
    conn.execute("DELETE FROM recipes WHERE name = ?", (name,))
    cur = conn.execute(
        "INSERT INTO recipes (name, time_minutes, effort) VALUES (?, ?, ?)",
        (name, time_minutes, effort),
    )
    recipe_id = cur.lastrowid

    seen = set()  # guard against the same ingredient listed twice
    for ingredient_name, quantity, unit in items:
        ingredient_id = ingredients.get_or_create(conn, ingredient_name)
        if ingredient_id in seen:
            raise ValueError(
                f"ingredient '{ingredient_name}' appears twice in recipe "
                f"'{name}' -- combine the rows instead"
            )
        seen.add(ingredient_id)
        conn.execute(
            "INSERT INTO recipe_ingredients "
            "  (recipe_id, ingredient_id, quantity, unit) "
            "VALUES (?, ?, ?, ?)",
            (recipe_id, ingredient_id, quantity, unit),
        )
    return recipe_id


def delete_recipe(conn, recipe_id):
    """Remove a recipe. Its recipe_ingredients rows cascade away via the
    FK. Does NOT commit."""
    cur = conn.execute("DELETE FROM recipes WHERE recipe_id = ?", (recipe_id,))
    return cur.rowcount > 0


# --- reads -----------------------------------------------------------------

def get_recipe(conn, recipe_id):
    """Return a recipe with its ingredient list, or None if not found.
    Shape:
        {
          recipe_id, name, time_minutes, effort,
          ingredients: [
            {ingredient_id, name, quantity, unit},
            ...
          ]
        }
    """
    head = conn.execute(
        "SELECT recipe_id, name, time_minutes, effort "
        "FROM recipes WHERE recipe_id = ?",
        (recipe_id,),
    ).fetchone()
    if head is None:
        return None

    rows = conn.execute("""
        SELECT i.ingredient_id, i.name, ri.quantity, ri.unit
        FROM recipe_ingredients ri
        JOIN ingredients i ON i.ingredient_id = ri.ingredient_id
        WHERE ri.recipe_id = ?
        ORDER BY i.name
    """, (recipe_id,)).fetchall()

    return {
        "recipe_id":    head["recipe_id"],
        "name":         head["name"],
        "time_minutes": head["time_minutes"],
        "effort":       head["effort"],
        "ingredients":  [dict(r) for r in rows],
    }


def list_recipes(conn):
    """All recipes, metadata only (no ingredients). For a browse view.
    Use get_recipe(id) to load one recipe's details."""
    return conn.execute(
        "SELECT recipe_id, name, time_minutes, effort "
        "FROM recipes ORDER BY name"
    ).fetchall()


# --- the headline: what can I cook right now? -----------------------------

def _ingredient_available(conn, ingredient_id, needed_qty, needed_unit):
    """The decision rule for a single recipe ingredient. Pulled out as its
    own function so the logic is easy to read -- and easy to flip to
    strict-units later by removing the 'optimistic mismatch' branch."""

    needed_qty = needed_qty or 0  # treat NULL recipe quantity as 0 = OK

    # 1. enough in the same unit? -> definitely available
    matched = conn.execute("""
        SELECT COALESCE(SUM(quantity_left), 0) AS total
        FROM inventory
        WHERE ingredient_id = ? AND unit = ? AND quantity_left > ?
    """, (ingredient_id, needed_unit, _EPS)).fetchone()["total"]
    if matched + _EPS >= needed_qty:
        return True

    # 2. not enough matching -- is there ANY stock in another unit?
    #    optimistic policy: assume that stock could cover the gap.
    #    flip this branch to `return False` for strict-units behavior.
    other = conn.execute("""
        SELECT COALESCE(SUM(quantity_left), 0) AS total
        FROM inventory
        WHERE ingredient_id = ? AND (unit IS NOT ? OR unit IS NULL)
              AND quantity_left > ?
    """, (ingredient_id, needed_unit, _EPS)).fetchone()["total"]
    if other > _EPS:
        return True

    # 3. nothing in any unit -> unavailable.
    return False


def get_makeable_recipes(conn):
    """Recipes where EVERY ingredient is available (strict yes/no).
    A recipe with zero ingredients is treated as not makeable.

    Unit-mismatch policy: optimistic. If a recipe asks for 400 g beans and
    you have beans only in 'can', it counts as available. See
    _ingredient_available() for the exact rule.

    Returns the same shape as list_recipes() -- just metadata. Use
    get_recipe(id) for the full detail."""
    makeable = []
    for recipe in list_recipes(conn):
        needs = conn.execute(
            "SELECT ingredient_id, quantity, unit "
            "FROM recipe_ingredients WHERE recipe_id = ?",
            (recipe["recipe_id"],),
        ).fetchall()
        if not needs:
            continue   # stub recipe, no ingredients -> not makeable
        if all(_ingredient_available(conn, n["ingredient_id"],
                                     n["quantity"], n["unit"])
               for n in needs):
            makeable.append(recipe)
    return makeable


# --- quick self-check ------------------------------------------------------

if __name__ == "__main__":
    import db
    import inventory

    conn = db.connect(":memory:")
    db.init_db(conn)

    # Two recipes from your screenshot
    add_recipe(conn, "Sunny side eggs with beans and toast", 15, "low", [
        ("Eggs",   2,   "whole"),
        ("Butter", 10,  "g"),
        ("Beans",  400, "g"),
        ("Toast",  2,   "slice"),
        ("Salt",   1,   "pinch"),
        ("Pepper", 1,   "pinch"),
    ])
    add_recipe(conn, "Chicken wrap", 20, "middle", [
        ("Chicken", 300, "g"),
        ("Wraps",   1,   "whole"),
    ])
    add_recipe(conn, "Stub: Milk rice", 10, "low", [])   # no ingredients yet

    # Replace-on-duplicate proof: re-adding the eggs recipe with edits.
    add_recipe(conn, "Sunny side eggs with beans and toast", 15, "low", [
        ("Eggs",   2,   "whole"),
        ("Butter", 10,  "g"),
        ("Beans",  400, "g"),
        ("Toast",  2,   "slice"),
        ("Salt",   1,   "pinch"),
        ("Pepper", 1,   "pinch"),
    ])
    print("Recipe count after re-add (should be 3):",
          len(list_recipes(conn)))
    print("recipe_ingredients count for eggs (should be 6):",
          conn.execute("""SELECT COUNT(*) FROM recipe_ingredients ri
                          JOIN recipes r USING(recipe_id)
                          WHERE r.name LIKE 'Sunny%'""").fetchone()[0])

    # Stock the kitchen for the eggs recipe but NOT the wrap.
    inventory.add_inventory(conn, "Eggs",   10, "whole", "fridge",
                            "2026-06-01", "2026-07-24", 3.0)
    inventory.add_inventory(conn, "Butter", 250, "g", "fridge",
                            "2026-06-01", "2026-08-01")
    inventory.add_inventory(conn, "Beans",  460, "g", "pantry",
                            "2026-06-01", "2026-10-01")
    inventory.add_inventory(conn, "Toast",  24, "slice", "pantry",
                            "2026-06-01", "2026-07-07")
    inventory.add_inventory(conn, "Salt",   100, "pinch", "pantry",
                            "2026-06-01", "2027-01-01")
    inventory.add_inventory(conn, "Pepper", 100, "pinch", "pantry",
                            "2026-06-01", "2027-01-01")
    # Note: no Chicken, no Wraps.
    conn.commit()

    print("\n=== get_recipe (full detail of eggs recipe) ===")
    eggs = next(r for r in list_recipes(conn) if r["name"].startswith("Sunny"))
    recipe = get_recipe(conn, eggs["recipe_id"])
    print(f"{recipe['name']}  ({recipe['time_minutes']} min, {recipe['effort']})")
    for ing in recipe["ingredients"]:
        print(f"  - {ing['quantity']:g} {ing['unit']:<6} {ing['name']}")

    print("\n=== What can I cook right now? ===")
    for r in get_makeable_recipes(conn):
        print(f"  - {r['name']}  ({r['time_minutes']} min, {r['effort']})")
    print("(Chicken Wrap should NOT appear -- no chicken, no wraps in stock.)")
    print("(Milk rice stub should NOT appear either -- no ingredients.)")

    print("\n=== Optimistic-mismatch behavior ===")
    # Wipe wraps stock, add wraps in 'piece' (mismatch with recipe's 'whole')
    # and add chicken in correct unit. Optimistic = should now be makeable.
    inventory.add_inventory(conn, "Chicken", 500, "g", "fridge",
                            "2026-06-20", "2026-07-01")
    inventory.add_inventory(conn, "Wraps",   8,   "piece", "pantry",
                            "2026-06-20", "2026-08-01")
    conn.commit()
    print("After adding chicken (g) and wraps in 'piece' (recipe wants 'whole'):")
    for r in get_makeable_recipes(conn):
        print(f"  - {r['name']}")
    print("(Chicken Wrap SHOULD appear now -- optimistic policy.)")

    conn.close()