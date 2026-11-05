"""Thin wrapper around the Notion API. Retries on HTTP 429."""


class NotionClient:
    def __init__(self, token: str, database_id: str):
        raise NotImplementedError

    def query_changed(self, since: str | None) -> list[dict]:
        """Pages edited after `since` (ISO timestamp); all pages if None."""
        raise NotImplementedError

    def list_all_page_ids(self) -> set[str]:
        """Every live page id. Used to detect deleted recipes."""
        raise NotImplementedError

    def get_page_text(self, page_id: str) -> str:
        """The page body as plain text (the ingredient lines)."""
        raise NotImplementedError
