"""
ai_extract.py
The AI part of this project. It has 3 main obligations:

1. Takes a receipt photo (and optionally a product photo)
and returns a clean list of ParsedItem objects describing what was
bought. This file does NOT touch the database -- the caller (the UI)
reviews the result with the user, then feeds confirmed items into
inventory.add_inventory().

2. Some form of text to speech

3. Some way to find receipes online

Stub-first design:
  - Default mode is STUB: returns hardcoded fake data, ignores the image,
    no network call, no API key needed, no money spent.
  - REAL mode calls the Anthropic API. Enable by either:
      * setting environment variable KITCHEN_AI_MODE=real, OR
      * passing use_stub=False to parse_receipt()
  - Both modes return the SAME shape, so nothing else in the app cares.

To use real mode you'll need:
  - pip install anthropic
  - ANTHROPIC_API_KEY environment variable set to your console key
"""

import os
import json
import base64
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional


# --- module config ---------------------------------------------------------

# Default to STUB unless explicitly told otherwise. Safer default --
# you have to opt in to spending money.
USE_STUB_DEFAULT = os.environ.get("KITCHEN_AI_MODE", "stub").lower() != "real"

# Which Claude model to use when in real mode. Sonnet is a good balance
# of vision quality + cost for receipts. Haiku is cheaper but less
# reliable on messy receipt OCR.
DEFAULT_MODEL = "claude-sonnet-4-6"

# Cap output so a runaway response can't run up the bill. A receipt
# parse should be well under this -- ~30 items at ~30 tokens each.
DEFAULT_MAX_TOKENS = 1024


# --- the data shape both modes return -------------------------------------

@dataclass
class ParsedItem:
    """One item the AI extracted from a receipt (or photo).

    Has the same fields whether produced by stub or real mode. The UI
    reviews these, lets the user edit, then maps confirmed items into
    inventory.add_inventory(name, quantity, unit, price=...).
    """
    name: str                          # AI's best guess at ingredient name
    quantity: float                    # numeric amount purchased
    unit: str                          # 'g', 'whole', 'slice', etc.
    price: Optional[float] = None      # total price for this line, if visible
    confidence: float = 1.0            # 0..1; UI uses this to flag uncertain rows
    raw_label: Optional[str] = None    # what the receipt actually said

    def to_dict(self):
        return asdict(self)


# --- public API ------------------------------------------------------------

def parse_receipt(receipt_image, product_photo=None,
                  known_ingredients=None, use_stub=None):
    """Extract items from a receipt photo.

    receipt_image:     path to the receipt image (str or Path).
                       Ignored in stub mode.
    product_photo:     optional path to a 'groceries on the counter' photo,
                       which can help disambiguate cryptic receipt labels.
                       Ignored in stub mode.
    known_ingredients: optional iterable of existing ingredient names from
                       your DB (e.g. [r['name'] for r in ingredients.list_all()]).
                       Real mode passes these into the prompt so the AI
                       prefers your existing vocabulary over inventing
                       new names ('whole milk' -> 'Milk').
    use_stub:          explicit override. None means follow USE_STUB_DEFAULT.

    Returns:           list[ParsedItem]
    """
    if use_stub is None:
        use_stub = USE_STUB_DEFAULT
    if use_stub:
        return _stub_parse(receipt_image, product_photo, known_ingredients)
    return _real_parse(receipt_image, product_photo, known_ingredients)


# --- stub implementation ---------------------------------------------------

def _stub_parse(receipt_image, product_photo, known_ingredients):
    """Fake data shaped like a real receipt parse. Lets the rest of the
    app be built and tested without touching the API."""
    # One deliberately low-confidence item ("Toast") so the UI review
    # flow has something to flag during development.
    return [
        ParsedItem(name="Eggs",   quantity=10,  unit="whole", price=3.50,
                   confidence=0.99, raw_label="EGGS L 10PK"),
        ParsedItem(name="Butter", quantity=250, unit="g",     price=2.40,
                   confidence=0.95, raw_label="BUTTER UNSALT 250G"),
        ParsedItem(name="Beans",  quantity=460, unit="g",     price=1.20,
                   confidence=0.90, raw_label="BAKED BEANS 460G"),
        ParsedItem(name="Toast",  quantity=1,   unit="whole", price=2.10,
                   confidence=0.55, raw_label="WHOLEMEAL LF"),
        ParsedItem(name="Pepper", quantity=50,  unit="g",     price=1.80,
                   confidence=0.85, raw_label="BLK PEPPER GRD"),
    ]


# --- real implementation ---------------------------------------------------

# Prompt is a module-level constant so it's easy to tune in one place.
_PROMPT_TEMPLATE = """\
You are helping extract grocery items from a receipt photo for a kitchen \
inventory app. Look at the image(s) and identify each grocery item.

For each item, output a JSON object with these fields:
  - name:       the ingredient name (string)
  - quantity:   numeric amount purchased (number)
  - unit:       one of: 'g', 'kg', 'ml', 'l', 'whole', 'slice', 'pinch', 'piece'
  - price:      total price paid for this line, or null if not visible (number/null)
  - confidence: your confidence in this extraction, 0.0 to 1.0 (number)
  - raw_label:  the exact text from the receipt for this line (string)

{vocab_block}\
Return ONLY a JSON array of these objects, no surrounding text, no markdown \
fences. Skip non-grocery lines (subtotal, tax, payment method, etc.).

Example output:
[{{"name":"Eggs","quantity":10,"unit":"whole","price":3.50,"confidence":0.95,"raw_label":"EGGS L 10PK"}}]
"""


def _real_parse(receipt_image, product_photo, known_ingredients):
    """The actual API call. Lazy-imports `anthropic` so stub mode users
    don't need the SDK installed."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
    
            "Real mode requires the anthropic package. "
            "Install with: pip install anthropic"
        )
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "Real mode requires ANTHROPIC_API_KEY env var. "
            "Get a key at https://console.anthropic.com"
        )

    # Build a `content` list with the image(s) followed by the prompt text.
    content = [_encode_image_block(receipt_image)]
    if product_photo:
        content.append(_encode_image_block(product_photo))
    content.append({"type": "text", "text": _build_prompt(known_ingredients)})

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=DEFAULT_MAX_TOKENS,
        messages=[{"role": "user", "content": content}],
    )

    # Response has one text block when max_tokens isn't hit.
    raw_text = response.content[0].text
    return _decode_response(raw_text)


def _encode_image_block(path):
    """Base64-encode an image file and wrap it for the Anthropic API.
    Detects media type from the file extension."""
    p = Path(path)
    data = p.read_bytes()
    b64 = base64.standard_b64encode(data).decode("ascii")
    ext = p.suffix.lower()
    media_type = {
        ".jpg":  "image/jpeg", ".jpeg": "image/jpeg",
        ".png":  "image/png",
        ".gif":  "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": b64},
    }


def _build_prompt(known_ingredients):
    """Insert the known-vocabulary block into the prompt template if we
    have one to pass."""
    if known_ingredients:
        names = sorted(set(known_ingredients))
        vocab_block = (
            "The kitchen already knows these ingredients -- prefer to "
            "match an item to one of these names rather than invent a new "
            "name when reasonable:\n  " + ", ".join(names) + "\n\n"
        )
    else:
        vocab_block = ""
    return _PROMPT_TEMPLATE.format(vocab_block=vocab_block)


def _decode_response(raw_text):
    """Turn the model's JSON-array response into ParsedItem objects.
    Tolerates accidental markdown fences and stray whitespace."""
    text = raw_text.strip()
    if text.startswith("```"):
        # strip ```json ... ``` fences if the model added them
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip("`").strip()
    try:
        items = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"AI response wasn't valid JSON: {e}\n--- raw response ---\n{raw_text}"
        )
    if not isinstance(items, list):
        raise RuntimeError(f"AI response wasn't a list. Got: {type(items).__name__}")

    parsed = []
    for it in items:
        parsed.append(ParsedItem(
            name=str(it["name"]),
            quantity=float(it["quantity"]),
            unit=str(it["unit"]),
            price=(float(it["price"]) if it.get("price") is not None else None),
            confidence=float(it.get("confidence", 1.0)),
            raw_label=it.get("raw_label"),
        ))
    return parsed


# --- quick self-check ------------------------------------------------------

if __name__ == "__main__":
    # Demonstrates stub mode end-to-end. Doesn't need an API key or network.
    print(f"USE_STUB_DEFAULT = {USE_STUB_DEFAULT}  "
          f"(set KITCHEN_AI_MODE=real to flip)\n")

    # Pretend we passed in the existing ingredient vocabulary. In real
    # code this would come from ingredients.list_all().
    known = ["Eggs", "Butter", "Beans", "Toast", "Salt", "Pepper"]

    items = parse_receipt("fake/path/receipt.jpg",
                          product_photo="fake/path/groceries.jpg",
                          known_ingredients=known)

    print(f"Parsed {len(items)} items from the (stubbed) receipt:\n")
    print(f"  {'confidence':>10}  {'name':<10} {'qty':>5} {'unit':<6} "
          f"{'price':>6}  raw label")
    print(f"  {'-'*10}  {'-'*10} {'-'*5} {'-'*6} {'-'*6}  {'-'*20}")
    for it in items:
        flag = "  " if it.confidence >= 0.8 else "!!"
        price = f"{it.price:.2f}" if it.price is not None else "  -- "
        print(f"{flag}{it.confidence:>9.2f}  {it.name:<10} {it.quantity:>5g} "
              f"{it.unit:<6} {price:>6}  {it.raw_label}")

    print("\n'!!' marks low-confidence rows the UI should flag for review.")
    print("After user review, each item becomes a call to "
          "inventory.add_inventory(name, quantity, unit, price=...).")