from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.providers.models import ensure_utc

from .models import PaperExitReason, PaperTrade, PaperTradeStatus


def _coerce_decimal(
    value: Decimal | float | int | str,
    *,
    field_name: str,
) -> Decimal:
    decimal_value = Decimal(str(value))
    if decimal_value < 0:
        raise ValueError(f"{field_name} must be zero or greater")
    return decimal_value


@dataclass(frozen=True, slots=True)
class ResponsiveExitPolicy:
    weak_follow_through_grace_seconds: int = 120
    min_progress_r_multiple: Decimal | float | int | str = "0.25"

    def __post_init__(self) -> None:
        if self.weak_follow_through_grace_seconds <= 0:
            raise ValueError("weak_follow_through_grace_seconds must be greater than zero")
        object.__setattr__(
            self,
            "min_progress_r_multiple",
            _coerce_decimal(self.min_progress_r_multiple, field_name="min_progress_r_multiple"),
        )


@dataclass(frozen=True, slots=True)
class PaperTradeObservation:
    observed_at: datetime
    high_price: Decimal | float | int | str
    low_price: Decimal | float | int | str
    close_price: Decimal | float | int | str
    best_price_since_entry: Decimal | float | int | str | None = None
    momentum_failed: bool = False
    momentum_note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, field_name="observed_at"))
        high_price = _coerce_decimal(self.high_price, field_name="high_price")
        low_price = _coerce_decimal(self.low_price, field_name="low_price")
        close_price = _coerce_decimal(self.close_price, field_name="close_price")
        object.__setattr__(self, "high_price", high_price)
        object.__setattr__(self, "low_price", low_price)
        object.__setattr__(self, "close_price", close_price)
        if low_price > high_price:
            raise ValueError("low_price cannot exceed high_price")
        if close_price < low_price or close_price > high_price:
            raise ValueError("close_price must stay within the observation range")

        best_price = high_price
        if self.best_price_since_entry is not None:
            best_price = _coerce_decimal(self.best_price_since_entry, field_name="best_price_since_entry")
        if best_price < high_price:
            raise ValueError("best_price_since_entry cannot be below the observed high_price")
        object.__setattr__(self, "best_price_since_entry", best_price)

        note = None if self.momentum_note is None else self.momentum_note.strip()
        if self.momentum_failed and note is None:
            note = "momentum_failed"
        if not self.momentum_failed and note is not None:
            raise ValueError("momentum_note requires momentum_failed=True")
        object.__setattr__(self, "momentum_note", note)


@dataclass(frozen=True, slots=True)
class ExitDecision:
    should_exit: bool
    reason: PaperExitReason | None = None
    close_price: Decimal | float | int | str | None = None
    observed_at: datetime | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if self.observed_at is not None:
            object.__setattr__(self, "observed_at", ensure_utc(self.observed_at, field_name="observed_at"))
        if self.close_price is not None:
            object.__setattr__(self, "close_price", _coerce_decimal(self.close_price, field_name="close_price"))
        note = None if self.note is None else self.note.strip()
        object.__setattr__(self, "note", note or None)

        if self.should_exit:
            if self.reason is None or self.close_price is None or self.observed_at is None:
                raise ValueError("exit decisions require reason, close_price, and observed_at")
        elif self.reason is not None or self.close_price is not None or self.observed_at is not None:
            raise ValueError("hold decisions cannot include exit fields")


def evaluate_exit(
    trade: PaperTrade,
    observation: PaperTradeObservation,
    *,
    exit_policy: ResponsiveExitPolicy | None = None,
) -> ExitDecision:
    if trade.status is not PaperTradeStatus.OPEN:
        raise ValueError("exit evaluation requires an open trade")

    policy = exit_policy or ResponsiveExitPolicy()

    # Conservative bar handling: when both stop and target print inside one bar,
    # assume the protective stop fired first.
    if observation.low_price <= trade.stop_price:
        return ExitDecision(
            True,
            reason=PaperExitReason.STOP_HIT,
            close_price=trade.stop_price,
            observed_at=observation.observed_at,
        )
    if observation.high_price >= trade.target_price:
        return ExitDecision(
            True,
            reason=PaperExitReason.TARGET_HIT,
            close_price=trade.target_price,
            observed_at=observation.observed_at,
        )
    if observation.momentum_failed:
        return ExitDecision(
            True,
            reason=PaperExitReason.MOMENTUM_FAILURE,
            close_price=observation.close_price,
            observed_at=observation.observed_at,
            note=observation.momentum_note,
        )

    grace_deadline = trade.opened_at + timedelta(seconds=policy.weak_follow_through_grace_seconds)
    required_progress_price = trade.fill_price + (trade.risk_per_share * policy.min_progress_r_multiple)
    if (
        observation.observed_at >= grace_deadline
        and observation.best_price_since_entry < required_progress_price
        and observation.close_price <= trade.fill_price
    ):
        return ExitDecision(
            True,
            reason=PaperExitReason.WEAK_FOLLOW_THROUGH,
            close_price=observation.close_price,
            observed_at=observation.observed_at,
            note="insufficient_progress_after_entry",
        )

    return ExitDecision(False)
