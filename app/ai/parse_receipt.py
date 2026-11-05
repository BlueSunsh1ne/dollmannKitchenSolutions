"""LATER (committed mode): receipt photo -> items to confirm.
Reuses the stub/real pattern from the old ai_extract.py."""

from dataclasses import dataclass

from app.ai.client import AIClient
from app.core.vocabulary import Ingredient


@dataclass
class ReceiptItem:
    raw_label: str
    ingredient_id: int | None
    name: str
    quantity: float | None
    unit: str | None
    price: float | None
    confidence: float


def parse_receipt(image: bytes, media_type: str, vocabulary: list[Ingredient], *,
                  client: AIClient | None = None) -> list[ReceiptItem]:
    """Photo of a receipt -> proposed purchases. Writes nothing."""
    raise NotImplementedError
