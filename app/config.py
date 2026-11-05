"""All settings read from the environment, in one place."""

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("KITCHEN_DB", BACKEND_DIR / "kitchen.db"))

AI_MODE = os.environ.get("KITCHEN_AI_MODE", "stub")          # 'stub' | 'real'
AI_MODEL = os.environ.get("KITCHEN_AI_MODEL", "claude-haiku-5-5")

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_RECIPES_DB = os.environ.get("NOTION_RECIPES_DB")

DEFAULT_MAX_MISSING = 2
