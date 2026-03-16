from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.providers.models import ensure_utc


def _coerce_decimal(
    value: Decimal | float | int | str,
    *,
    field_name: str,
    allow_negative: bool = False,
) -> Decimal:
    decimal_value = Decimal(str(value))
    if not allow_negative and decimal_value < 0:
        raise ValueError(f"{field_name} must be zero or greater")
    return decimal_value


class TradeGateReason(StrEnum):
    MISSING_STOP = "missing_stop"
    SPREAD_TOO_WIDE = "spread_too_wide"
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"
    STOP_DISTANCE_TOO_WIDE = "stop_distance_too_wide"


class SessionBlockReason(StrEnum):
    MAX_DAILY_LOSS_REACHED = "max_daily_loss_reached"
    MAX_OPEN_POSITIONS = "max_open_positions"
    ENTRY_CUTOFF_REACHED = "entry_cutoff_reached"
    COOLDOWN_ACTIVE = "cooldown_active"


class EntryDisposition(StrEnum):
    ACTIONABLE = "actionable"
    BLOCKED = "blocked"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class RiskDefaults:
    risk_per_trade_fraction: Decimal | float | int | str = "0.01"
    max_daily_loss_fraction: Decimal | float | int | str = "0.03"
    max_open_positions: int = 1
    max_spread_percent: Decimal | float | int | str = "0.75"
    min_average_daily_volume: int = 500_000
    entry_cutoff_hour: int = 15
    entry_cutoff_minute: int = 30
    trading_timezone: str = "America/New_York"
    cooldown_after_loss_seconds: int = 600
    cooldown_after_consecutive_losses_seconds: int = 1800

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "risk_per_trade_fraction",
            _coerce_decimal(self.risk_per_trade_fraction, field_name="risk_per_trade_fraction"),
        )
        object.__setattr__(
            self,
            "max_daily_loss_fraction",
            _coerce_decimal(self.max_daily_loss_fraction, field_name="max_daily_loss_fraction"),
        )
        object.__setattr__(
            self,
            "max_spread_percent",
            _coerce_decimal(self.max_spread_percent, field_name="max_spread_percent"),
        )
        if self.max_open_positions <= 0:
            raise ValueError("max_open_positions must be greater than zero")
        if self.min_average_daily_volume < 0:
            raise ValueError("min_average_daily_volume must be zero or greater")
        if not 0 <= self.entry_cutoff_hour <= 23:
            raise ValueError("entry_cutoff_hour must be between 0 and 23")
        if not 0 <= self.entry_cutoff_minute <= 59:
            raise ValueError("entry_cutoff_minute must be between 0 and 59")
        if self.cooldown_after_loss_seconds < 0:
            raise ValueError("cooldown_after_loss_seconds must be zero or greater")
        if self.cooldown_after_consecutive_losses_seconds < 0:
            raise ValueError("cooldown_after_consecutive_losses_seconds must be zero or greater")
        if not self.trading_timezone.strip():
            raise ValueError("trading_timezone must not be empty")


@dataclass(frozen=True, slots=True)
class PositionSize:
    quantity: int
    risk_budget: Decimal | float | int | str
    risk_per_share: Decimal | float | int | str
    estimated_notional: Decimal | float | int | str

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        object.__setattr__(self, "risk_budget", _coerce_decimal(self.risk_budget, field_name="risk_budget"))
        object.__setattr__(self, "risk_per_share", _coerce_decimal(self.risk_per_share, field_name="risk_per_share"))
        object.__setattr__(
            self,
            "estimated_notional",
            _coerce_decimal(self.estimated_notional, field_name="estimated_notional"),
        )


@dataclass(frozen=True, slots=True)
class TradeQualitySnapshot:
    average_daily_volume: Decimal | float | int | str | None
    spread_percent: Decimal | float | int | str | None = None
    live_liquidity_thin: bool = False

    def __post_init__(self) -> None:
        if self.average_daily_volume is not None:
            object.__setattr__(
                self,
                "average_daily_volume",
                _coerce_decimal(self.average_daily_volume, field_name="average_daily_volume"),
            )
        if self.spread_percent is not None:
            object.__setattr__(
                self,
                "spread_percent",
                _coerce_decimal(self.spread_percent, field_name="spread_percent"),
            )


@dataclass(frozen=True, slots=True)
class TradeGateDecision:
    passed: bool
    reason: TradeGateReason | None = None
    position_size: PositionSize | None = None

    def __post_init__(self) -> None:
        if self.passed:
            if self.reason is not None:
                raise ValueError("passed trade gates cannot include a rejection reason")
            if self.position_size is None:
                raise ValueError("passed trade gates require a position_size")
        else:
            if self.reason is None:
                raise ValueError("failed trade gates require a reason")
            if self.position_size is not None:
                raise ValueError("failed trade gates cannot include a position_size")


@dataclass(frozen=True, slots=True)
class SessionState:
    account_equity: Decimal | float | int | str
    realized_pnl_today: Decimal | float | int | str = "0"
    open_positions: int = 0
    last_loss_at: datetime | None = None
    consecutive_losses: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "account_equity", _coerce_decimal(self.account_equity, field_name="account_equity"))
        object.__setattr__(
            self,
            "realized_pnl_today",
            _coerce_decimal(self.realized_pnl_today, field_name="realized_pnl_today", allow_negative=True),
        )
        if self.open_positions < 0:
            raise ValueError("open_positions must be zero or greater")
        if self.consecutive_losses < 0:
            raise ValueError("consecutive_losses must be zero or greater")
        if self.last_loss_at is not None:
            object.__setattr__(self, "last_loss_at", ensure_utc(self.last_loss_at, field_name="last_loss_at"))


@dataclass(frozen=True, slots=True)
class SessionGuardDecision:
    allowed: bool
    reason: SessionBlockReason | None = None
    blocked_until: datetime | None = None

    def __post_init__(self) -> None:
        if self.blocked_until is not None:
            object.__setattr__(self, "blocked_until", ensure_utc(self.blocked_until, field_name="blocked_until"))
        if self.allowed:
            if self.reason is not None or self.blocked_until is not None:
                raise ValueError("allowed session decisions cannot include block metadata")
        else:
            if self.reason is None:
                raise ValueError("blocked session decisions require a reason")


@dataclass(frozen=True, slots=True)
class EntryEligibility:
    disposition: EntryDisposition
    reason: TradeGateReason | SessionBlockReason | None = None
    position_size: PositionSize | None = None
    blocked_until: datetime | None = None

    def __post_init__(self) -> None:
        if self.blocked_until is not None:
            object.__setattr__(self, "blocked_until", ensure_utc(self.blocked_until, field_name="blocked_until"))
        if self.disposition is EntryDisposition.ACTIONABLE:
            if self.position_size is None:
                raise ValueError("actionable entries require a position_size")
            if self.reason is not None or self.blocked_until is not None:
                raise ValueError("actionable entries cannot include block metadata")
        elif self.disposition is EntryDisposition.BLOCKED:
            if self.reason is None:
                raise ValueError("blocked entries require a reason")
            if self.position_size is not None:
                raise ValueError("blocked entries cannot include a position_size")
        elif self.disposition is EntryDisposition.REJECTED:
            if self.reason is None:
                raise ValueError("rejected entries require a reason")
            if self.position_size is not None or self.blocked_until is not None:
                raise ValueError("rejected entries cannot include sizing or blocked_until")
