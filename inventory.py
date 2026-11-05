"""
inventory.py
The stock layer. Owns the `inventory` table.

Inventory rows are PURCHASE EVENTS, not "current state". Each row records
one batch: what was bought, how much, when, where it lives, expiry, price.
quantity_left tracks consumption -- so an empty batch (quantity_left = 0)
stays in the table as purchase history. consume() updates quantity_left
to 0; it does NOT delete the row.

Writes:
  add_inventory()    -- record a purchase
  consume()          -- drain stock after a meal / snack
  clear_inventory()  -- DEV TOOL, deletes rows (history and all)

Reads (for the dashboard):
  get_all_active()         -- every batch with stock remaining
  aggregate_by_ingredient -- per-ingredient totals (collapsed across batches)
  get_expiring_soon()      -- the 'use it up' band
  get_running_low()        -- ingredients below their par level
"""

import ingredients

# floating-point dust tolerance: treat anything within this of zero as zero.
_EPS = 1e-9


# --- writes ----------------------------------------------------------------

def add_inventory(conn, ingredient_name, quantity_buy, unit,
                  location=None, buy_date=None, expiry_date=None, price=None):
    """Record a new purchase. Auto-creates the ingredient if it's new.

    quantity_left is initialized to quantity_buy -- a fresh batch is full.
    Dates should be ISO 'YYYY-MM-DD' so they sort chronologically.

    Returns the new inventory_id (the handle to this specific batch).
    Does NOT commit -- the caller decides when to persist.
    """
    if quantity_buy <= 0:
        raise ValueError("quantity_buy must be positive")

    ingredient_id = ingredients.get_or_create(conn, ingredient_name)
    cur = conn.execute(
        "INSERT INTO inventory "
        "  (ingredient_id, quantity_buy, quantity_left, unit, "
        "   location, buy_date, expiry_date, price) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ingredient_id, quantity_buy, quantity_buy, unit,
         location, buy_date, expiry_date, price),
    )
    return cur.lastrowid


def consume(conn, items):
    """Subtract consumed ingredients from inventory after a meal/snack.

    items: list of (ingredient_name, quantity, unit) tuples.

    Behavior:
      - Drains matching batches SOONEST-EXPIRY-FIRST (NULL dates last).
      - When a batch hits zero, quantity_left is set to 0 (row stays as
        purchase history). It is NOT deleted.
      - Refuses to subtract across a unit mismatch (no silent conversion).
      - Returns a list of human-readable notes describing what happened.

    Does NOT commit. Caller commits (or rolls back to undo).
    """
    report = []
    for name, qty_needed, unit in items:
        if qty_needed is None or qty_needed <= _EPS:
            report.append(f"{name}: quantity 0 or missing, skipped.")
            continue

        ing_row = ingredients.get_by_name(conn, name)
        if ing_row is None:
            report.append(f"{name}: unknown ingredient, skipped.")
            continue
        ingredient_id = ing_row["ingredient_id"]

        # Matching live batches, soonest expiry first. NULL dates sorted last
        # (the boolean (expiry_date IS NULL) is 0 for real dates, 1 for NULL).
        batches = conn.execute("""
            SELECT inventory_id, quantity_left
            FROM inventory
            WHERE ingredient_id = ?
              AND unit = ?
              AND quantity_left > ?
            ORDER BY (expiry_date IS NULL), expiry_date
        """, (ingredient_id, unit, _EPS)).fetchall()

        if not batches:
            # No matching batches -- explain why (mismatch vs out of stock).
            other_units = [r["unit"] for r in conn.execute(
                "SELECT DISTINCT unit FROM inventory "
                "WHERE ingredient_id = ? AND quantity_left > ?",
                (ingredient_id, _EPS),
            )]
            if other_units:
                units_str = ", ".join(u or "(none)" for u in other_units)
                report.append(
                    f"{name}: asked for '{unit}' but stock is in '{units_str}' "
                    "- unit mismatch, nothing deducted."
                )
            else:
                report.append(f"{name}: out of stock, nothing to deduct.")
            continue

        remaining = qty_needed
        for batch in batches:
            if remaining <= _EPS:
                break
            take = min(batch["quantity_left"], remaining)
            new_left = batch["quantity_left"] - take
            if new_left <= _EPS:
                new_left = 0.0
            conn.execute(
                "UPDATE inventory SET quantity_left = ? WHERE inventory_id = ?",
                (new_left, batch["inventory_id"]),
            )
            remaining -= take

        if remaining > _EPS:
            report.append(
                f"{name}: drained all stock but still short {remaining:g} {unit}."
            )
        else:
            report.append(f"{name}: deducted {qty_needed:g} {unit}.")
    return report


def clear_inventory(conn, location=None):
    """DEV TOOL. Deletes inventory rows -- including the purchase-history
    rows where quantity_left = 0. Use only for resetting test data.

        clear_inventory(conn)             -> wipe everything
        clear_inventory(conn, "fridge")   -> wipe fridge rows only

    Returns the number of rows deleted. Does NOT commit.
    """
    if location is None:
        cur = conn.execute("DELETE FROM inventory")
    else:
        cur = conn.execute("DELETE FROM inventory WHERE location = ?", (location,))
    return cur.rowcount


# --- reads -----------------------------------------------------------------

def get_all_active(conn):
    """Every batch with stock remaining, joined to the ingredient name.
    Ordered by expiry (soonest first) so the riskiest things float up.
    This is the data source for the dashboard's main list."""
    return conn.execute("""
        SELECT v.inventory_id, i.name AS ingredient,
               v.quantity_buy, v.quantity_left, v.unit,
               v.location, v.buy_date, v.expiry_date, v.price
        FROM inventory v
        JOIN ingredients i ON i.ingredient_id = v.ingredient_id
        WHERE v.quantity_left > :eps
        ORDER BY (v.expiry_date IS NULL), v.expiry_date, i.name
    """, {"eps": _EPS}).fetchall()


def aggregate_by_ingredient(conn):
    """Collapse batches into one row per (ingredient, unit), summing
    quantity_left and surfacing the soonest expiry as the flag date.

    Why (ingredient, unit) and not just ingredient: you might have eggs
    counted in 'whole' and (hypothetically) in 'g'. They aren't directly
    comparable, so they stay as separate aggregate rows -- no fake summing.
    """
    return conn.execute("""
        SELECT i.ingredient_id, i.name AS ingredient, v.unit,
               SUM(v.quantity_left) AS total_left,
               MIN(v.expiry_date)   AS earliest_expiry,
               COUNT(*)             AS batch_count
        FROM inventory v
        JOIN ingredients i ON i.ingredient_id = v.ingredient_id
        WHERE v.quantity_left > :eps
        GROUP BY i.ingredient_id, v.unit
        ORDER BY (earliest_expiry IS NULL), earliest_expiry, i.name
    """, {"eps": _EPS}).fetchall()


def get_expiring_soon(conn, within_days=5):
    """Batches expiring within N days (from today). Powers the 'needs
    attention' band on the dashboard."""
    return conn.execute("""
        SELECT v.inventory_id, i.name AS ingredient,
               v.quantity_left, v.unit, v.location, v.expiry_date,
               CAST(julianday(v.expiry_date) - julianday('now') AS INTEGER)
                   AS days_left
        FROM inventory v
        JOIN ingredients i ON i.ingredient_id = v.ingredient_id
        WHERE v.quantity_left > :eps
          AND v.expiry_date IS NOT NULL
          AND julianday(v.expiry_date) - julianday('now') <= :days
        ORDER BY v.expiry_date
    """, {"eps": _EPS, "days": within_days}).fetchall()


def get_running_low(conn):
    """Ingredients below their par level (min_quantity).

    Comparison is unit-matched: only inventory rows whose `unit` equals the
    ingredient's `min_unit` count toward the total. If you set the par in
    'whole' but have stock only in 'g', the function honestly reports
    total = 0 -- a deliberate prompt for you to reconcile units, not a
    silent guess.
    """
    return conn.execute("""
        SELECT i.ingredient_id, i.name AS ingredient,
               i.min_quantity, i.min_unit,
               COALESCE(SUM(
                   CASE WHEN v.unit = i.min_unit AND v.quantity_left > :eps
                        THEN v.quantity_left END
               ), 0) AS total_in_min_unit
        FROM ingredients i
        LEFT JOIN inventory v ON v.ingredient_id = i.ingredient_id
        WHERE i.min_quantity IS NOT NULL
        GROUP BY i.ingredient_id
        HAVING total_in_min_unit < i.min_quantity
        ORDER BY (total_in_min_unit / i.min_quantity), i.name
    """, {"eps": _EPS}).fetchall()


# --- quick self-check ------------------------------------------------------

if __name__ == "__main__":
    import db

    conn = db.connect(":memory:")
    db.init_db(conn)

    # Load the data from your latest screenshot. Dates converted to ISO.
    add_inventory(conn, "Eggs",   10,  "whole", "fridge", "2026-06-01", "2026-07-24", 3.0)
    add_inventory(conn, "Butter", 250, "g",     "fridge", "2026-06-01", "2026-08-01", None)
    add_inventory(conn, "Beans",  460, "g",     "pantry", "2026-06-01", "2026-10-01", None)
    add_inventory(conn, "Toast",  24,  "slice", "pantry", "2026-06-01", "2026-07-07", None)
    add_inventory(conn, "Salt",   100, "pinch", "pantry", "2026-06-01", "2027-01-01", None)
    add_inventory(conn, "Pepper", 100, "pinch", "pantry", "2026-06-01", "2027-01-01", None)
    add_inventory(conn, "Eggs",   10,  "whole", "fridge", "2026-06-10", "2026-09-01", 4.0)

    # Mirror the screenshot's "quantity_left" by consuming the difference.
    # (Your screenshot shows e.g. eggs batch 1 at 3-left from 10-bought.)
    consume(conn, [("Eggs", 7, "whole"), ("Butter", 50, "g"),
                   ("Toast", 9, "slice"), ("Pepper", 40, "pinch")])
    # Drain salt to zero to exercise the purchase-history-stays behavior.
    consume(conn, [("Salt", 100, "pinch")])

    # Par levels, for get_running_low.
    eggs_id   = ingredients.get_by_name(conn, "Eggs")["ingredient_id"]
    butter_id = ingredients.get_by_name(conn, "Butter")["ingredient_id"]
    salt_id   = ingredients.get_by_name(conn, "Salt")["ingredient_id"]
    ingredients.set_par_level(conn, eggs_id,   6,   "whole")  # we have 13, OK
    ingredients.set_par_level(conn, butter_id, 300, "g")      # we have 200, LOW
    ingredients.set_par_level(conn, salt_id,   50,  "pinch")  # we have 0, LOW

    conn.commit()

    print("=== Aggregated by ingredient (the dashboard's main list) ===")
    for r in aggregate_by_ingredient(conn):
        print(f"  {r['ingredient']:<8} {r['total_left']:>6g} {r['unit']:<6} "
              f"earliest expiry {r['earliest_expiry']}  "
              f"({r['batch_count']} batch{'es' if r['batch_count']>1 else ''})")

    print("\n=== Expiring within 60 days (band) ===")
    for r in get_expiring_soon(conn, within_days=60):
        print(f"  {r['ingredient']:<8} {r['quantity_left']:g} {r['unit']:<6} "
              f"in {r['location']} -- {r['days_left']} day(s) left")

    print("\n=== Running low (below par level) ===")
    for r in get_running_low(conn):
        print(f"  {r['ingredient']:<8} have {r['total_in_min_unit']:g} {r['min_unit']}, "
              f"want at least {r['min_quantity']:g}")

    print("\n=== Edge cases ===")
    for note in consume(conn, [
            ("Beans",  3,    "whole"),   # mismatch: stocked in g
            ("Cheese", 1,    "slice"),   # unknown ingredient
            ("Eggs",   999,  "whole")]): # more than we have
        print("  -", note)

    print("\n=== Purchase history preserved? ===")
    salt_history = conn.execute("""
        SELECT v.quantity_buy, v.quantity_left, v.price, v.buy_date
        FROM inventory v JOIN ingredients i ON i.ingredient_id = v.ingredient_id
        WHERE i.name = 'Salt'""").fetchall()
    for r in salt_history:
        print(f"  Salt bought {r['quantity_buy']:g} on {r['buy_date']}, "
              f"now {r['quantity_left']:g} left (row preserved as history).")

    conn.close()