"""Data models for the intelligence layer — sentiment analysis and adaptive learning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum


class SentimentDirection(StrEnum):
    STRONGLY_BULLISH = "strongly_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONGLY_BEARISH = "strongly_bearish"


class CatalystQuality(StrEnum):
    """How actionable the catalyst is for a momentum day-trade."""
    TIER_1 = "tier_1"  # FDA approval, major contract, M&A — highest conviction
    TIER_2 = "tier_2"  # Earnings beat, upgrade, product launch
    TIER_3 = "tier_3"  # Sector rotation, analyst mention, social buzz
    NOISE = "noise"    # Irrelevant or recycled news


@dataclass(frozen=True, slots=True)
class SentimentVerdict:
    """LLM-generated interpretation of a news catalyst."""
    headline: str
    symbol: str
    direction: SentimentDirection
    catalyst_quality: CatalystQuality
    confidence: float  # 0.0 to 1.0
    expected_move_percent: float | None  # LLM's estimate of price impact
    reasoning: str  # One-line LLM explanation
    analyzed_at: datetime

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if self.analyzed_at.tzinfo is None or self.analyzed_at.utcoffset() is None:
            raise ValueError("analyzed_at must be timezone-aware")
        object.__setattr__(self, "analyzed_at", self.analyzed_at.astimezone(UTC))

    @property
    def score_multiplier(self) -> Decimal:
        """Convert sentiment into a scoring multiplier (0.5x to 1.5x)."""
        direction_map = {
            SentimentDirection.STRONGLY_BULLISH: Decimal("1.4"),
            SentimentDirection.BULLISH: Decimal("1.15"),
            SentimentDirection.NEUTRAL: Decimal("1.0"),
            SentimentDirection.BEARISH: Decimal("0.7"),
            SentimentDirection.STRONGLY_BEARISH: Decimal("0.5"),
        }
        quality_map = {
            CatalystQuality.TIER_1: Decimal("1.1"),
            CatalystQuality.TIER_2: Decimal("1.0"),
            CatalystQuality.TIER_3: Decimal("0.9"),
            CatalystQuality.NOISE: Decimal("0.6"),
        }
        base = direction_map.get(self.direction, Decimal("1.0"))
        quality = quality_map.get(self.catalyst_quality, Decimal("1.0"))
        confidence_weight = Decimal(str(self.confidence))
        # Blend: higher confidence = more influence from LLM verdict
        blended = Decimal("1.0") + (base * quality - Decimal("1.0")) * confidence_weight
        return max(Decimal("0.5"), min(Decimal("1.5"), blended))


class TradeOutcome(StrEnum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    OPEN = "open"


@dataclass(frozen=True, slots=True)
class OutcomeRecord:
    """A completed trade with its entry features and result — used for learning."""
    trade_id: str
    symbol: str
    entered_at: datetime
    closed_at: datetime | None
    # Entry features (snapshot of conditions when trade was entered)
    catalyst_tag: str
    catalyst_quality: str | None  # From LLM if available
    sentiment_direction: str | None
    sentiment_confidence: float | None
    entry_price: Decimal
    stop_price: Decimal | None
    target_price: Decimal | None
    score_at_entry: int
    daily_rvol: Decimal | None
    short_term_rvol: Decimal | None
    change_percent: Decimal | None
    gap_percent: Decimal | None
    hour_of_day: int  # 0-23 UTC
    # Result
    exit_price: Decimal | None = None
    realized_pnl: Decimal | None = None
    outcome: TradeOutcome = TradeOutcome.OPEN

    def __post_init__(self) -> None:
        if self.entered_at.tzinfo is None:
            raise ValueError("entered_at must be timezone-aware")
        object.__setattr__(self, "entered_at", self.entered_at.astimezone(UTC))
        if self.closed_at is not None:
            if self.closed_at.tzinfo is None:
                raise ValueError("closed_at must be timezone-aware")
            object.__setattr__(self, "closed_at", self.closed_at.astimezone(UTC))


@dataclass(frozen=True, slots=True)
class AdaptiveAdjustment:
    """Score adjustment derived from historical trade outcomes."""
    catalyst_type_adjustment: Decimal  # -10 to +10 based on win rate by catalyst
    rvol_range_adjustment: Decimal     # -5 to +5 based on RVOL performance
    time_of_day_adjustment: Decimal    # -5 to +5 based on hour performance
    sentiment_accuracy_adjustment: Decimal  # -5 to +5 based on LLM hit rate
    total_adjustment: Decimal = Decimal("0")
    sample_size: int = 0
    reasoning: str = ""

    def __post_init__(self) -> None:
        total = (
            self.catalyst_type_adjustment
            + self.rvol_range_adjustment
            + self.time_of_day_adjustment
            + self.sentiment_accuracy_adjustment
        )
        # Clamp total to [-15, +15]
        clamped = max(Decimal("-15"), min(Decimal("15"), total))
        object.__setattr__(self, "total_adjustment", clamped)
