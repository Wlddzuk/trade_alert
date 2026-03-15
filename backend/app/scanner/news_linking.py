from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime

from app.providers.models import NewsEvent, normalize_symbol

from .models import LinkedNewsEvent


def news_timestamp(event: NewsEvent) -> datetime:
    return event.updated_at or event.published_at


def first_news_at(linked_news: LinkedNewsEvent | None) -> datetime | None:
    if linked_news is None:
        return None
    first_timestamp = min((news_timestamp(event) for event in linked_news.related_events), default=None)
    return first_timestamp.astimezone(UTC) if first_timestamp is not None else None


def catalyst_age_seconds(
    linked_news: LinkedNewsEvent | None,
    *,
    observed_at: datetime,
) -> float | None:
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")

    first_timestamp = first_news_at(linked_news)
    if first_timestamp is None:
        return None
    age = observed_at.astimezone(UTC) - first_timestamp
    return max(age.total_seconds(), 0.0)


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
