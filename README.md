# Kitchen backend: skeleton

Structure and function signatures only; bodies raise NotImplementedError.
Put `backend/` next to `datasets/` in the repo.

## Minimal version (quick mode) = build these first
1. `app/db/connection.py` + `schema.sql` (schema is final for v1)
2. `app/core/vocabulary.py` + `scripts/seed_vocabulary.py`
3. `app/core/recipes.py`
4. `app/core/matcher.py`
5. `app/ai/client.py` + `app/ai/interpret.py`
6. `scripts/quick.py`

## Later
- `app/sync/`: Notion -> SQLite
- `app/stock/`, `app/ai/parse_receipt.py`: committed mode
- `app/api/`: HTTP layer for the phone (not created yet)

## Flow
speech -> text (phone) -> interpret() -> user confirms -> confirm()
-> get_recipes_from_ingredients() -> recipes
