from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.providers.models import InstrumentRecord, to_decimal


class EligibilityReason(StrEnum):
    MISSING_METADATA = "missing_metadata"
    EXCHANGE_NOT_ALLOWED = "exchange_not_allowed"
    NOT_COMMON_STOCK = "not_common_stock"
    EXCLUDED_INSTRUMENT_TYPE = "excluded_instrument_type"
    PRICE_OUTSIDE_RANGE = "price_outside_range"
    ADV_BELOW_MINIMUM = "adv_below_minimum"


@dataclass(frozen=True, slots=True)
class UniverseCandidate:
    symbol: str
    exchange: str | None
    is_common_stock: bool | None
    instrument_type: str | None
    last_price: Decimal | float | int | str | None
    average_daily_volume: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(
            self,
            "exchange",
            self.exchange.strip().upper() if self.exchange else None,
        )
        object.__setattr__(
            self,
            "instrument_type",
            self.instrument_type.strip().lower() if self.instrument_type else None,
        )
        object.__setattr__(self, "last_price", to_decimal(self.last_price, field_name="last_price"))
        if self.average_daily_volume is not None and self.average_daily_volume < 0:
            raise ValueError("average_daily_volume must be zero or greater")

    @classmethod
    def from_instrument_record(
        cls,
        record: InstrumentRecord,
        *,
        last_price: Decimal | float | int | str | None,
    ) -> "UniverseCandidate":
        return cls(
            symbol=record.symbol,
            exchange=record.exchange,
            is_common_stock=record.is_common_stock,
            instrument_type=record.security_type.value,
            last_price=last_price,
            average_daily_volume=record.average_daily_volume,
        )


@dataclass(frozen=True, slots=True)
class UniverseRules:
    min_price: Decimal = Decimal("1.50")
    max_price: Decimal = Decimal("20.00")
    min_average_daily_volume: int = 500_000
    allowed_exchanges: frozenset[str] = frozenset({"NASDAQ", "NYSE"})
    excluded_instrument_types: frozenset[str] = frozenset(
        {
            "otc",
            "etf",
            "warrant",
            "preferred",
            "rights",
            "closed_end_fund",
            "adr",
        }
    )


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    candidate: UniverseCandidate
    eligible: bool
    reasons: tuple[EligibilityReason, ...]
