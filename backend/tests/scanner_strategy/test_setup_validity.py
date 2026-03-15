from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.providers.models import CatalystTag, NewsEvent
from app.scanner.news_linking import catalyst_age_seconds, latest_news_for_symbol
from app.scanner.strategy_defaults import StrategyDefaults
from app.scanner.strategy_models import InvalidReason, SetupValidity


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
    assert defaults.min_move_on_day_percent == Decimal("8")
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
