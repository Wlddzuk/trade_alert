from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Generic, TypeVar


class ProviderCapability(StrEnum):
    MARKET_DATA = "market_data"
    NEWS = "news"


class ProviderHealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    UNAVAILABLE = "unavailable"


class SecurityType(StrEnum):
    COMMON_STOCK = "common_stock"
    ADR = "adr"
    ETF = "etf"
    WARRANT = "warrant"
    UNIT = "unit"
    OTHER = "other"


class CatalystTag(StrEnum):
    BREAKING_NEWS = "breaking_news"
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    OFFERING = "offering"
    M_AND_A = "m_and_a"
    FDA = "fda"
    ANALYST = "analyst"
    GENERAL = "general"
    UNKNOWN = "unknown"


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("symbol must not be empty")
    return normalized


def normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if not normalized:
        raise ValueError("provider must not be empty")
    return normalized


def ensure_utc(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def to_decimal(value: Decimal | float | int | str | None, *, field_name: str) -> Decimal | None:
    if value is None:
        return None
    decimal_value = Decimal(str(value))
    if decimal_value < 0:
        raise ValueError(f"{field_name} must be zero or greater")
    return decimal_value


@dataclass(frozen=True, slots=True)
class InstrumentRecord:
    symbol: str
    exchange: str
    security_type: SecurityType
    is_common_stock: bool
    average_daily_volume: int | None
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        object.__setattr__(self, "exchange", self.exchange.strip().upper())
        object.__setattr__(self, "updated_at", ensure_utc(self.updated_at, field_name="updated_at"))
        if self.average_daily_volume is not None and self.average_daily_volume < 0:
            raise ValueError("average_daily_volume must be zero or greater")


@dataclass(frozen=True, slots=True)
class ProviderHealthSnapshot:
    provider: str
    capability: ProviderCapability
    observed_at: datetime
    last_update_at: datetime | None
    freshness_age_seconds: float | None
    state: ProviderHealthState
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", normalize_provider(self.provider))
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, field_name="observed_at"))
        if self.last_update_at is not None:
            object.__setattr__(
                self,
                "last_update_at",
                ensure_utc(self.last_update_at, field_name="last_update_at"),
            )
        if self.freshness_age_seconds is not None and self.freshness_age_seconds < 0:
            raise ValueError("freshness_age_seconds must be zero or greater")


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    symbol: str
    provider: str
    observed_at: datetime
    received_at: datetime
    last_price: Decimal | float | int | str
    session_volume: int
    previous_close: Decimal | float | int | str | None = None
    open_price: Decimal | float | int | str | None = None
    high_price: Decimal | float | int | str | None = None
    low_price: Decimal | float | int | str | None = None
    vwap: Decimal | float | int | str | None = None
    exchange: str | None = None
    currency: str = "USD"

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        object.__setattr__(self, "provider", normalize_provider(self.provider))
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, field_name="observed_at"))
        object.__setattr__(self, "received_at", ensure_utc(self.received_at, field_name="received_at"))
        object.__setattr__(self, "last_price", to_decimal(self.last_price, field_name="last_price"))
        object.__setattr__(
            self,
            "previous_close",
            to_decimal(self.previous_close, field_name="previous_close"),
        )
        object.__setattr__(self, "open_price", to_decimal(self.open_price, field_name="open_price"))
        object.__setattr__(self, "high_price", to_decimal(self.high_price, field_name="high_price"))
        object.__setattr__(self, "low_price", to_decimal(self.low_price, field_name="low_price"))
        object.__setattr__(self, "vwap", to_decimal(self.vwap, field_name="vwap"))
        if self.session_volume < 0:
            raise ValueError("session_volume must be zero or greater")
        if self.exchange is not None:
            object.__setattr__(self, "exchange", self.exchange.strip().upper())


@dataclass(frozen=True, slots=True)
class DailyBar:
    symbol: str
    provider: str
    trading_date: date
    observed_at: datetime
    open_price: Decimal | float | int | str
    high_price: Decimal | float | int | str
    low_price: Decimal | float | int | str
    close_price: Decimal | float | int | str
    volume: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        object.__setattr__(self, "provider", normalize_provider(self.provider))
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, field_name="observed_at"))
        object.__setattr__(self, "open_price", to_decimal(self.open_price, field_name="open_price"))
        object.__setattr__(self, "high_price", to_decimal(self.high_price, field_name="high_price"))
        object.__setattr__(self, "low_price", to_decimal(self.low_price, field_name="low_price"))
        object.__setattr__(self, "close_price", to_decimal(self.close_price, field_name="close_price"))
        if isinstance(self.trading_date, datetime):
            object.__setattr__(
                self,
                "trading_date",
                ensure_utc(self.trading_date, field_name="trading_date").date(),
            )
        elif not isinstance(self.trading_date, date):
            raise ValueError("trading_date must be a date")
        if self.volume < 0:
            raise ValueError("volume must be zero or greater")


@dataclass(frozen=True, slots=True)
class IntradayBar:
    symbol: str
    provider: str
    start_at: datetime
    interval_minutes: int
    open_price: Decimal | float | int | str
    high_price: Decimal | float | int | str
    low_price: Decimal | float | int | str
    close_price: Decimal | float | int | str
    volume: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        object.__setattr__(self, "provider", normalize_provider(self.provider))
        object.__setattr__(self, "start_at", ensure_utc(self.start_at, field_name="start_at"))
        object.__setattr__(self, "open_price", to_decimal(self.open_price, field_name="open_price"))
        object.__setattr__(self, "high_price", to_decimal(self.high_price, field_name="high_price"))
        object.__setattr__(self, "low_price", to_decimal(self.low_price, field_name="low_price"))
        object.__setattr__(self, "close_price", to_decimal(self.close_price, field_name="close_price"))
        if self.interval_minutes <= 0:
            raise ValueError("interval_minutes must be greater than zero")
        if self.volume < 0:
            raise ValueError("volume must be zero or greater")


@dataclass(frozen=True, slots=True)
class NewsEvent:
    event_id: str
    provider: str
    published_at: datetime
    received_at: datetime
    headline: str
    symbols: tuple[str, ...]
    channels: tuple[str, ...] = ()
    authors: tuple[str, ...] = ()
    updated_at: datetime | None = None
    summary: str | None = None
    url: str | None = None
    catalyst_tag: CatalystTag = CatalystTag.UNKNOWN
    is_correction: bool = False

    def __post_init__(self) -> None:
        cleaned_headline = self.headline.strip()
        if not cleaned_headline:
            raise ValueError("headline must not be empty")
        object.__setattr__(self, "headline", cleaned_headline)
        object.__setattr__(self, "provider", normalize_provider(self.provider))
        object.__setattr__(self, "published_at", ensure_utc(self.published_at, field_name="published_at"))
        object.__setattr__(self, "received_at", ensure_utc(self.received_at, field_name="received_at"))
        if self.updated_at is not None:
            object.__setattr__(self, "updated_at", ensure_utc(self.updated_at, field_name="updated_at"))
        object.__setattr__(self, "symbols", tuple(normalize_symbol(symbol) for symbol in self.symbols))
        object.__setattr__(self, "channels", tuple(channel.strip() for channel in self.channels if channel.strip()))
        object.__setattr__(self, "authors", tuple(author.strip() for author in self.authors if author.strip()))
        object.__setattr__(self, "event_id", str(self.event_id).strip())
        if not self.event_id:
            raise ValueError("event_id must not be empty")


RecordT = TypeVar("RecordT")


@dataclass(frozen=True, slots=True)
class ProviderBatch(Generic[RecordT]):
    provider: str
    capability: ProviderCapability
    fetched_at: datetime
    records: tuple[RecordT, ...]
    health: ProviderHealthSnapshot
    cursor: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", normalize_provider(self.provider))
        object.__setattr__(self, "fetched_at", ensure_utc(self.fetched_at, field_name="fetched_at"))
        object.__setattr__(self, "records", tuple(self.records))
        if self.provider != self.health.provider:
            raise ValueError("health snapshot provider must match batch provider")
        if self.capability != self.health.capability:
            raise ValueError("health snapshot capability must match batch capability")

    def __len__(self) -> int:
        return len(self.records)
