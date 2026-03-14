from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime

from app.providers.models import NewsEvent, normalize_symbol

from .models import LinkedNewsEvent


def news_timestamp(event: NewsEvent) -> datetime:
    return event.updated_at or event.published_at


def latest_news_for_symbol(
    symbol: str,
    events: Iterable[NewsEvent],
) -> LinkedNewsEvent | None:
    normalized_symbol = normalize_symbol(symbol)
    matching = tuple(event for event in events if normalized_symbol in event.symbols)
    if not matching:
        return None

    ordered = tuple(sorted(matching, key=news_timestamp, reverse=True))
    latest = ordered[0]
    return LinkedNewsEvent(
        symbol=normalized_symbol,
        latest_event=latest,
        latest_event_at=news_timestamp(latest),
        related_events=ordered,
    )


def latest_news_by_symbol(events: Iterable[NewsEvent]) -> dict[str, LinkedNewsEvent]:
    by_symbol: dict[str, list[NewsEvent]] = defaultdict(list)
    for event in events:
        for symbol in event.symbols:
            by_symbol[symbol].append(event)

    return {
        symbol: latest_news_for_symbol(symbol, symbol_events)
        for symbol, symbol_events in by_symbol.items()
        if latest_news_for_symbol(symbol, symbol_events) is not None
    }
