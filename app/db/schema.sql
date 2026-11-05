-- Schema version 1 (stored in PRAGMA user_version).
-- CREATE ... IF NOT EXISTS makes init_db safe on every startup.
-- Changing a table here does NOT migrate an existing DB: bump the
-- version in connection.py and write a migration instead.

-- The vocabulary: one row per ingredient, nothing else.
-- ingredient_id matches the Ingredient_id column in
-- datasets/ingredient_id_list.xlsx, so the sheet stays the reference.
-- Names are unique ignoring case ('Eggs' and 'eggs' can't both exist).
CREATE TABLE IF NOT EXISTS ingredients (
    ingredient_id INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    category      TEXT,                      -- coarse, informal (Dairy, Spice, ...)
    container     TEXT,                      -- Glas, Can, Bag, ...
    default_unit  TEXT,                      -- 'g' / 'ml' / 'count'
    is_staple     INTEGER NOT NULL DEFAULT 0 CHECK (is_staple IN (0, 1)),
    min_quantity  REAL,                      -- par level for 'running low' (later)
    min_unit      TEXT
);

-- Recipes. Once the Notion sync exists, this table is a read-only mirror:
-- notion_page_id is how the sync recognizes a recipe it has seen before.
CREATE TABLE IF NOT EXISTS recipes (
    recipe_id          INTEGER PRIMARY KEY,
    name               TEXT NOT NULL,
    time_minutes       INTEGER,
    effort             TEXT,                 -- 'low' / 'middle' / 'high'
    servings           INTEGER,
    notion_page_id     TEXT UNIQUE,
    notion_last_edited TEXT,                 -- ISO timestamp from Notion
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_id     INTEGER NOT NULL
        REFERENCES recipes(recipe_id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL
        REFERENCES ingredients(ingredient_id) ON DELETE RESTRICT,
    quantity      REAL,                      -- NULL = 'some' / to taste
    unit          TEXT,
    optional      INTEGER NOT NULL DEFAULT 0 CHECK (optional IN (0, 1)),
    raw_text      TEXT,                      -- original line, e.g. '300 g chicken'
    PRIMARY KEY (recipe_id, ingredient_id)
);

-- Stock (fully committed mode). Unchanged from the first version for now;
-- it gets reworked in the stock step (percentage model, scraps).
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id   INTEGER PRIMARY KEY,
    ingredient_id  INTEGER NOT NULL
        REFERENCES ingredients(ingredient_id) ON DELETE RESTRICT,
    quantity_buy   REAL NOT NULL,
    quantity_left  REAL NOT NULL,
    unit           TEXT,
    location       TEXT,
    buy_date       TEXT,
    expiry_date    TEXT,
    price          REAL
);

CREATE INDEX IF NOT EXISTS idx_recipe_ing_ingredient ON recipe_ingredients(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_inventory_ingredient  ON inventory(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_inventory_expiry      ON inventory(expiry_date);
