from __future__ import annotations

from collections.abc import Sequence

from app.providers.base import MarketDataProvider, normalize_symbols
from app.providers.models import MarketSnapshot, ProviderBatch


class MarketIngestor:
    """Fetches the latest normalized market snapshots from the configured provider."""

    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider

    async def pull_latest(self, symbols: Sequence[str]) -> ProviderBatch[MarketSnapshot]:
        normalized_symbols = normalize_symbols(symbols)
        return await self._provider.fetch_market_snapshots(normalized_symbols)
