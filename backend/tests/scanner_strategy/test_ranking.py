from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.providers.models import CatalystTag
from app.scanner.context_features import ContextFeatures
from app.scanner.feed_service import CandidateFeedService
from app.scanner.invalidation import InvalidationDecision, TriggerInvalidationReason
from app.scanner.models import CandidateRow
from app.scanner.strategy_models import InvalidReason, SetupValidity
from app.scanner.strategy_ranking import score_candidate
from app.scanner.trigger_logic import TriggerEvaluation


def _row(symbol: str, *, change: str, daily_rvol: str, short_term_rvol: str) -> CandidateRow:
    observed_at = datetime(2026, 3, 14, 13, 40, tzinfo=UTC)
    return CandidateRow(
        symbol=symbol,
        headline=f"{symbol} update",
        catalyst_tag=CatalystTag.GENERAL,
        latest_news_at=observed_at,
        time_since_news_seconds=300.0,
        observed_at=observed_at,
        price=Decimal("24.00"),
        volume=1_500_000,
        average_daily_volume=Decimal("1000000"),
        daily_relative_volume=Decimal(daily_rvol),
        short_term_relative_volume=Decimal(short_term_rvol),
        gap_percent=Decimal("10.0"),
        change_from_prior_close_percent=Decimal(change),
        pullback_from_high_percent=Decimal("5.0"),
        why_surfaced="general | move=12% | daily_rvol=3x",
    )


def _features(*, pullback_volume_lighter: bool | None = None) -> ContextFeatures:
    return ContextFeatures(
        observed_at=datetime(2026, 3, 14, 13, 40, tzinfo=UTC),
        vwap=Decimal("22.00"),
        ema_9=Decimal("24.00"),
        ema_20=Decimal("23.00"),
        pullback_low=Decimal("23.00"),
        pullback_retracement_percent=Decimal("40.00"),
        pullback_volume_lighter=pullback_volume_lighter,
    )


def _validity(*, valid: bool = True) -> SetupValidity:
    return SetupValidity(
        setup_valid=valid,
        evaluated_at=datetime(2026, 3, 14, 13, 40, tzinfo=UTC),
        first_catalyst_at=datetime(2026, 3, 14, 13, 0, tzinfo=UTC),
        catalyst_age_seconds=2400.0,
        primary_invalid_reason=None if valid else InvalidReason.STALE_CATALYST,
    )


@dataclass(frozen=True, slots=True)
class _ProjectionStub:
    row: CandidateRow
    score: int
    is_valid: bool


def test_score_candidate_rewards_valid_quality_over_invalid_state() -> None:
    valid_score = score_candidate(
        _row("AAPL", change="18.0", daily_rvol="4.0", short_term_rvol="3.0"),
        context_features=_features(pullback_volume_lighter=True),
        setup_validity=_validity(valid=True),
        trigger_evaluation=TriggerEvaluation(
            triggered=True,
            interval_seconds=15,
            used_fallback=False,
            trigger_price=Decimal("24.10"),
            trigger_bar_started_at=datetime(2026, 3, 14, 13, 40, tzinfo=UTC),
            bullish_confirmation=True,
        ),
    )
    invalid_score = score_candidate(
        _row("MSFT", change="20.0", daily_rvol="5.0", short_term_rvol="4.0"),
        context_features=_features(),
        setup_validity=_validity(valid=False),
        invalidation=InvalidationDecision(True, TriggerInvalidationReason.SETUP_INVALID),
    )

    assert valid_score > invalid_score
    assert 0 <= invalid_score <= 100
    assert 0 <= valid_score <= 100


def test_order_strategy_rows_keeps_valid_rows_above_invalid_and_higher_scores_first() -> None:
    service = CandidateFeedService()
    valid_projection = _ProjectionStub(
        row=_row("AAPL", change="18.0", daily_rvol="4.0", short_term_rvol="3.0"),
        score=92,
        is_valid=True,
    )
    weaker_valid_projection = _ProjectionStub(
        row=_row("NVDA", change="10.0", daily_rvol="2.2", short_term_rvol="1.8"),
        score=71,
        is_valid=True,
    )
    invalid_projection = _ProjectionStub(
        row=_row("MSFT", change="20.0", daily_rvol="5.0", short_term_rvol="4.0"),
        score=99,
        is_valid=False,
    )

    ordered = service.order_strategy_rows((invalid_projection, weaker_valid_projection, valid_projection))

    assert [projection.row.symbol for projection in ordered] == ["AAPL", "NVDA", "MSFT"]
