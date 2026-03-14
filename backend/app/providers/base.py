from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from .models import MarketSnapshot, NewsEvent, ProviderBatch


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def normalize_symbols(symbols: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        candidate = symbol.strip().upper()
        if not candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return tuple(normalized)


class JsonFetcher(Protocol):
    async def __call__(self, url: str, params: Mapping[str, Any]) -> Any:
        ...


class MarketDataProvider(ABC):
    provider_name: str

    @abstractmethod
    async def fetch_market_snapshots(
        self,
        symbols: Sequence[str],
    ) -> ProviderBatch[MarketSnapshot]:
        ...


class NewsProvider(ABC):
    provider_name: str

    @abstractmethod
    async def fetch_recent_news(
        self,
        symbols: Sequence[str],
        *,
        updated_since: datetime | None = None,
        limit: int = 100,
    ) -> ProviderBatch[NewsEvent]:
        ...
