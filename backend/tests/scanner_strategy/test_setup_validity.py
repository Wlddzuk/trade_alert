from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.providers.models import CatalystTag, IntradayBar, NewsEvent
from app.scanner.context_features import ContextFeatures, build_context_features
from app.scanner.models import CandidateRow
from app.scanner.news_linking import catalyst_age_seconds, latest_news_for_symbol
from app.scanner.setup_validity import evaluate_setup_validity
from app.scanner.strategy_defaults import StrategyDefaults
from app.scanner.strategy_models import InvalidReason, SetupValidity


def _linked_news(
    *,
    first_published_at: datetime,
    latest_published_at: datetime,
) -> object:
    events = (
        NewsEvent(
            event_id="1",
            provider="benzinga",
            published_at=first_published_at,
            received_at=first_published_at,
            headline="AAPL initial catalyst",
            symbols=("AAPL",),
            catalyst_tag=CatalystTag.BREAKING_NEWS,
        ),
        NewsEvent(
            event_id="2",
            provider="benzinga",
            published_at=latest_published_at,
            received_at=latest_published_at,
            headline="AAPL follow-up update",
            symbols=("AAPL",),
            catalyst_tag=CatalystTag.GENERAL,
        ),
    )
    linked_news = latest_news_for_symbol("AAPL", events)
    assert linked_news is not None
    return linked_news


def _candidate_row(
    *,
    observed_at: datetime,
    change_percent: str = "12.0",
    daily_rvol: str = "3.0",
    short_term_rvol: str = "2.0",
    price: str = "24.00",
) -> CandidateRow:
    return CandidateRow(
        symbol="AAPL",
        headline="AAPL follow-up update",
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
        change_from_prior_close_percent=Decimal(change_percent),
        pullback_from_high_percent=Decimal("5.0"),
        why_surfaced="general | move=12% | daily_rvol=3x",
    )


def test_catalyst_age_uses_first_related_headline() -> None:
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
            headline="AAPL follow-up update",
            symbols=("AAPL",),
            catalyst_tag=CatalystTag.GENERAL,
        ),
    )

    linked_news = latest_news_for_symbol("AAPL", events)
    assert linked_news is not None
    assert catalyst_age_seconds(linked_news, observed_at=datetime(2026, 3, 14, 13, 40, tzinfo=UTC)) == 2400.0


def test_strategy_defaults_expose_phase_three_defaults() -> None:
    defaults = StrategyDefaults()

    assert defaults.max_catalyst_age_minutes == 90
    assert defaults.min_move_on_day_percent == Decimal("5")
    assert defaults.min_daily_relative_volume == Decimal("2.0")
    assert defaults.min_short_term_relative_volume == Decimal("1.5")
    assert defaults.min_pullback_retracement_percent == Decimal("35")
    assert defaults.max_pullback_retracement_percent == Decimal("60")
    assert defaults.preferred_trigger_interval_seconds == 15
    assert defaults.fallback_trigger_interval_seconds == 60


def test_setup_validity_requires_primary_invalid_reason_for_invalid_rows() -> None:
    with pytest.raises(ValueError, match="invalid setups must have a primary_invalid_reason"):
        SetupValidity(
            setup_valid=False,
            evaluated_at=datetime(2026, 3, 14, 13, 40, tzinfo=UTC),
            first_catalyst_at=datetime(2026, 3, 14, 13, 0, tzinfo=UTC),
            catalyst_age_seconds=2400.0,
        )

    invalid = SetupValidity(
        setup_valid=False,
        evaluated_at=datetime(2026, 3, 14, 13, 40, tzinfo=UTC),
        first_catalyst_at=datetime(2026, 3, 14, 13, 0, tzinfo=UTC),
        catalyst_age_seconds=2400.0,
        primary_invalid_reason=InvalidReason.STALE_CATALYST,
    )
    assert invalid.primary_invalid_reason is InvalidReason.STALE_CATALYST


def test_build_context_features_calculates_ema_alignment_and_retracement() -> None:
    observed_at = datetime(2026, 3, 14, 13, 40, tzinfo=UTC)
    bars = tuple(
        IntradayBar(
            symbol="AAPL",
            provider="polygon",
            start_at=datetime(2026, 3, 14, 13, index, tzinfo=UTC),
            interval_minutes=1,
            open_price=str(10 + index),
            high_price=str(11 + index),
            low_price=str(9 + index),
            close_price=str(10 + index),
            volume=100_000 + index,
        )
        for index in range(20)
    )
    from app.providers.models import MarketSnapshot

    snapshot = MarketSnapshot(
        symbol="AAPL",
        provider="polygon",
        observed_at=observed_at,
        received_at=observed_at,
        last_price="24.00",
        session_volume=1_500_000,
        previous_close="21.00",
        open_price="22.00",
        high_price="30.00",
        low_price="10.00",
        vwap="22.00",
    )

    features = build_context_features(
        snapshot,
        bars,
        impulse_low=Decimal("10.00"),
        pullback_low=Decimal("23.00"),
    )

    assert features.vwap == Decimal("22.00")
    assert features.ema_9 is not None
    assert features.ema_20 is not None
    assert features.ema_9 > features.ema_20
    assert features.pullback_retracement_percent == Decimal("35.00")


def test_evaluate_setup_validity_returns_valid_when_candidate_matches_defaults() -> None:
    observed_at = datetime(2026, 3, 14, 13, 40, tzinfo=UTC)
    linked_news = _linked_news(
        first_published_at=datetime(2026, 3, 14, 13, 0, tzinfo=UTC),
        latest_published_at=datetime(2026, 3, 14, 13, 25, tzinfo=UTC),
    )
    row = _candidate_row(observed_at=observed_at)
    features = ContextFeatures(
        observed_at=observed_at,
        vwap=Decimal("22.00"),
        ema_9=Decimal("24.00"),
        ema_20=Decimal("23.00"),
        pullback_low=Decimal("23.00"),
        pullback_retracement_percent=Decimal("40.00"),
    )

    validity = evaluate_setup_validity(row, linked_news, features)

    assert validity.setup_valid is True
    assert validity.primary_invalid_reason is None
    assert validity.catalyst_age_seconds == 2400.0


def test_evaluate_setup_validity_uses_first_headline_age_for_stale_catalyst() -> None:
    observed_at = datetime(2026, 3, 14, 13, 40, tzinfo=UTC)
    linked_news = _linked_news(
        first_published_at=datetime(2026, 3, 14, 12, 0, tzinfo=UTC),
        latest_published_at=datetime(2026, 3, 14, 13, 25, tzinfo=UTC),
    )
    row = _candidate_row(observed_at=observed_at)
    features = ContextFeatures(
        observed_at=observed_at,
        vwap=Decimal("22.00"),
        ema_9=Decimal("24.00"),
        ema_20=Decimal("23.00"),
        pullback_low=Decimal("23.00"),
        pullback_retracement_percent=Decimal("40.00"),
    )

    validity = evaluate_setup_validity(row, linked_news, features)

    assert validity.setup_valid is False
    assert validity.primary_invalid_reason is InvalidReason.STALE_CATALYST


def test_evaluate_setup_validity_rejects_weak_relative_volume() -> None:
    observed_at = datetime(2026, 3, 14, 13, 40, tzinfo=UTC)
    linked_news = _linked_news(
        first_published_at=datetime(2026, 3, 14, 13, 0, tzinfo=UTC),
        latest_published_at=datetime(2026, 3, 14, 13, 25, tzinfo=UTC),
    )
    row = _candidate_row(observed_at=observed_at, daily_rvol="1.2")
    features = ContextFeatures(
        observed_at=observed_at,
        vwap=Decimal("22.00"),
        ema_9=Decimal("24.00"),
        ema_20=Decimal("23.00"),
        pullback_low=Decimal("23.00"),
        pullback_retracement_percent=Decimal("40.00"),
    )

    validity = evaluate_setup_validity(row, linked_news, features)

    assert validity.setup_valid is False
    assert validity.primary_invalid_reason is InvalidReason.INSUFFICIENT_DAILY_RVOL


def test_evaluate_setup_validity_rejects_price_below_vwap_before_pullback_checks() -> None:
    observed_at = datetime(2026, 3, 14, 13, 40, tzinfo=UTC)
    linked_news = _linked_news(
        first_published_at=datetime(2026, 3, 14, 13, 0, tzinfo=UTC),
        latest_published_at=datetime(2026, 3, 14, 13, 25, tzinfo=UTC),
    )
    row = _candidate_row(observed_at=observed_at, price="21.50")
    features = ContextFeatures(
        observed_at=observed_at,
        vwap=Decimal("22.00"),
        ema_9=Decimal("24.00"),
        ema_20=Decimal("23.00"),
        pullback_low=Decimal("23.00"),
        pullback_retracement_percent=Decimal("40.00"),
    )

    validity = evaluate_setup_validity(row, linked_news, features)

    assert validity.setup_valid is False
    assert validity.primary_invalid_reason is InvalidReason.BELOW_VWAP


def test_evaluate_setup_validity_rejects_pullback_too_deep() -> None:
    observed_at = datetime(2026, 3, 14, 13, 40, tzinfo=UTC)
    linked_news = _linked_news(
        first_published_at=datetime(2026, 3, 14, 13, 0, tzinfo=UTC),
        latest_published_at=datetime(2026, 3, 14, 13, 25, tzinfo=UTC),
    )
    row = _candidate_row(observed_at=observed_at)
    features = ContextFeatures(
        observed_at=observed_at,
        vwap=Decimal("22.00"),
        ema_9=Decimal("24.00"),
        ema_20=Decimal("23.00"),
        pullback_low=Decimal("18.00"),
        pullback_retracement_percent=Decimal("65.00"),
    )

    validity = evaluate_setup_validity(row, linked_news, features)

    assert validity.setup_valid is False
    assert validity.primary_invalid_reason is InvalidReason.PULLBACK_TOO_DEEP
