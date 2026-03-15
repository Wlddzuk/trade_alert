from __future__ import annotations

from collections.abc import Sequence

from app.providers.base import MarketDataProvider, normalize_symbols
from app.providers.models import DailyBar, IntradayBar, ProviderBatch


class MarketHistoryService:
    """Fetches normalized historical market bars for scanner baseline calculations."""

    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider

    async def pull_daily_bars(
        self,
        symbols: Sequence[str],
        *,
        lookback_days: int = 20,
    ) -> ProviderBatch[DailyBar]:
        normalized_symbols = normalize_symbols(symbols)
        return await self._provider.fetch_daily_bars(
            normalized_symbols,
            lookback_days=lookback_days,
        )

    async def pull_intraday_bars(
        self,
        symbols: Sequence[str],
        *,
        interval_minutes: int | None = 5,
        interval_seconds: int | None = None,
        lookback_days: int = 20,
    ) -> ProviderBatch[IntradayBar]:
        normalized_symbols = normalize_symbols(symbols)
        return await self._provider.fetch_intraday_bars(
            normalized_symbols,
            interval_minutes=interval_minutes,
            interval_seconds=interval_seconds,
            lookback_days=lookback_days,
        )
