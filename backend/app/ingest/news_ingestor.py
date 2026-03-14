from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from app.providers.base import NewsProvider, normalize_symbols
from app.providers.models import NewsEvent, ProviderBatch


class NewsIngestor:
    """Fetches the latest normalized news events from the configured provider."""

    def __init__(self, provider: NewsProvider) -> None:
        self._provider = provider

    async def pull_recent(
        self,
        symbols: Sequence[str],
        *,
        updated_since: datetime | None = None,
        limit: int = 100,
    ) -> ProviderBatch[NewsEvent]:
        normalized_symbols = normalize_symbols(symbols)
        return await self._provider.fetch_recent_news(
            normalized_symbols,
            updated_since=updated_since,
            limit=limit,
        )
