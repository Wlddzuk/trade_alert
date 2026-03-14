from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.providers.models import CatalystTag, NewsEvent, normalize_symbol


@dataclass(frozen=True, slots=True)
class LinkedNewsEvent:
    symbol: str
    latest_event: NewsEvent
    latest_event_at: datetime
    related_events: tuple[NewsEvent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        if self.latest_event_at.tzinfo is None or self.latest_event_at.utcoffset() is None:
            raise ValueError("latest_event_at must be timezone-aware")
        object.__setattr__(self, "latest_event_at", self.latest_event_at.astimezone(UTC))
        object.__setattr__(self, "related_events", tuple(self.related_events))

    @property
    def headline(self) -> str:
        return self.latest_event.headline

    @property
    def catalyst_tag(self) -> CatalystTag:
        return self.latest_event.catalyst_tag


@dataclass(frozen=True, slots=True)
class CandidateRow:
    symbol: str
    headline: str
    catalyst_tag: CatalystTag
    latest_news_at: datetime
    time_since_news_seconds: float
    observed_at: datetime
    price: Decimal | None
    volume: int
    average_daily_volume: Decimal | None
    daily_relative_volume: Decimal | None
    short_term_relative_volume: Decimal | None
    gap_percent: Decimal | None
    change_from_prior_close_percent: Decimal | None
    pullback_from_high_percent: Decimal | None
    why_surfaced: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        if self.latest_news_at.tzinfo is None or self.latest_news_at.utcoffset() is None:
            raise ValueError("latest_news_at must be timezone-aware")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        object.__setattr__(self, "latest_news_at", self.latest_news_at.astimezone(UTC))
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))
        if self.time_since_news_seconds < 0:
            raise ValueError("time_since_news_seconds must be zero or greater")
        if self.volume < 0:
            raise ValueError("volume must be zero or greater")
