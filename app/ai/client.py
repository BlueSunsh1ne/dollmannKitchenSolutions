"""Every LLM call goes through here. Stub mode costs nothing and is
what the tests use; real mode calls the Anthropic API."""

from typing import Protocol

from app.core.vocabulary import Ingredient


class AIClient(Protocol):
    def extract_ingredients(self, text: str,
                            vocabulary: list[Ingredient]) -> list[dict]:
        """Return [{'said': str, 'ingredient_id': int | None,
                    'new_name': str | None}, ...]"""
        ...


class StubClient:
    """Fake answers: splits on commas, exact name matches, rest is 'new'."""

    def extract_ingredients(self, text: str,
                            vocabulary: list[Ingredient]) -> list[dict]:
        raise NotImplementedError


class AnthropicClient:
    """Real calls, JSON output forced via a schema."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        raise NotImplementedError

    def extract_ingredients(self, text: str,
                            vocabulary: list[Ingredient]) -> list[dict]:
        raise NotImplementedError


def get_client(mode: str | None = None) -> AIClient:
    """'stub' or 'real'; defaults to config.AI_MODE."""
    raise NotImplementedError
