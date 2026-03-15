from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.providers.models import CatalystTag, NewsEvent
from app.scanner.context_features import ContextFeatures
from app.scanner.invalidation import TriggerInvalidationReason, evaluate_invalidation
from app.scanner.models import CandidateRow
from app.scanner.news_linking import latest_news_for_symbol
from app.scanner.strategy_models import SetupValidity


def _linked_news(*, correction: bool = False):
    events = (
        NewsEvent(
            event_id="1",
            provider="benzinga",
            published_at=datetime(2026, 3, 14, 13, 0, tzinfo=UTC),
            received_at=datetime(2026, 3, 14, 13, 0, tzinfo=UTC),
            headline="AAPL initial catalyst",
            symbols=("AAPL",),
            catalyst_tag=CatalystTag.BREAKING_NEWS,
        ),
        NewsEvent(
            event_id="2",
            provider="benzinga",
            published_at=datetime(2026, 3, 14, 13, 25, tzinfo=UTC),
            received_at=datetime(2026, 3, 14, 13, 25, tzinfo=UTC),
            headline="AAPL update",
            symbols=("AAPL",),
            catalyst_tag=CatalystTag.GENERAL,
            is_correction=correction,
        ),
    )
    linked_news = latest_news_for_symbol("AAPL", events)
    assert linked_news is not None
    return linked_news


def _row(*, price: str = "24.00", daily_rvol: str = "3.0", short_term_rvol: str = "2.0") -> CandidateRow:
    observed_at = datetime(2026, 3, 14, 13, 40, tzinfo=UTC)
    return CandidateRow(
        symbol="AAPL",
        headline="AAPL update",
        catalyst_tag=CatalystTag.GENERAL,
        latest_news_at=observed_at,
        time_since_news_seconds=300.0,
        observed_at=observed_at,
        price=Decimal(price),
        volume=1_500_000,
        average_daily_volume=Decimal("1000000"),
        daily_relative_volume=Decimal(daily_rvol),
        short_term_relative_volume=Decimal(short_term_rvol),
        gap_percent=Decimal("10.0"),
        change_from_prior_close_percent=Decimal("12.0"),
        pullback_from_high_percent=Decimal("5.0"),
        why_surfaced="general | move=12% | daily_rvol=3x",
    )


def _validity() -> SetupValidity:
    return SetupValidity(
        setup_valid=True,
        evaluated_at=datetime(2026, 3, 14, 13, 40, tzinfo=UTC),
        first_catalyst_at=datetime(2026, 3, 14, 13, 0, tzinfo=UTC),
        catalyst_age_seconds=2400.0,
    )


def _context(
    *,
    vwap: str = "22.00",
    ema20: str = "21.50",
    pullback_low: str = "22.00",
    retracement: str = "40.00",
) -> ContextFeatures:
    return ContextFeatures(
        observed_at=datetime(2026, 3, 14, 13, 40, tzinfo=UTC),
        vwap=Decimal(vwap),
        ema_9=Decimal("24.00"),
        ema_20=Decimal(ema20),
        pullback_low=Decimal(pullback_low),
        pullback_retracement_percent=Decimal(retracement),
    )


def test_evaluate_invalidation_detects_contradictory_correction_news() -> None:
    decision = evaluate_invalidation(_row(), _linked_news(correction=True), _context(), setup_validity=_validity())

    assert decision.invalidated is True
    assert decision.reason is TriggerInvalidationReason.CONTRADICTORY_CATALYST


def test_evaluate_invalidation_detects_pullback_low_break() -> None:
    decision = evaluate_invalidation(
        _row(price="21.90"),
        _linked_news(),
        _context(vwap="21.00", ema20="20.50", pullback_low="22.00"),
        setup_validity=_validity(),
    )

    assert decision.invalidated is True
    assert decision.reason is TriggerInvalidationReason.PULLBACK_LOW_BROKEN


def test_evaluate_invalidation_detects_lost_intraday_context() -> None:
    decision = evaluate_invalidation(
        _row(price="21.00"),
        _linked_news(),
        _context(vwap="22.00", ema20="21.50", pullback_low="20.50"),
        setup_validity=_validity(),
    )

    assert decision.invalidated is True
    assert decision.reason is TriggerInvalidationReason.LOST_INTRADAY_CONTEXT


def test_evaluate_invalidation_detects_halt_and_dead_move_conditions() -> None:
    halted = evaluate_invalidation(_row(), _linked_news(), _context(), setup_validity=_validity(), halt_active=True)
    dead_move = evaluate_invalidation(
        _row(),
        _linked_news(),
        _context(),
        setup_validity=_validity(),
        failed_breakout_attempts=2,
    )

    assert halted.reason is TriggerInvalidationReason.HALTED
    assert dead_move.reason is TriggerInvalidationReason.DEAD_MOVE


def test_evaluate_invalidation_detects_weak_relative_volume_before_trigger() -> None:
    decision = evaluate_invalidation(
        _row(daily_rvol="1.2"),
        _linked_news(),
        _context(),
        setup_validity=_validity(),
    )

    assert decision.invalidated is True
    assert decision.reason is TriggerInvalidationReason.WEAK_RELATIVE_VOLUME
