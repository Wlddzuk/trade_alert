from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.providers.models import CatalystTag
from app.scanner.context_features import ContextFeatures
from app.scanner.invalidation import InvalidationDecision, TriggerInvalidationReason
from app.scanner.models import CandidateRow
from app.scanner.strategy_models import InvalidReason, SetupValidity
from app.scanner.strategy_projection import project_strategy_row
from app.scanner.strategy_tags import StrategyStageTag
from app.scanner.trigger_logic import TriggerEvaluation


def _row() -> CandidateRow:
    observed_at = datetime(2026, 3, 14, 13, 40, tzinfo=UTC)
    return CandidateRow(
        symbol="AAPL",
        headline="AAPL update",
        catalyst_tag=CatalystTag.GENERAL,
        latest_news_at=observed_at,
        time_since_news_seconds=300.0,
        observed_at=observed_at,
        price=Decimal("24.00"),
        volume=1_500_000,
        average_daily_volume=Decimal("1000000"),
        daily_relative_volume=Decimal("3.0"),
        short_term_relative_volume=Decimal("2.0"),
        gap_percent=Decimal("10.0"),
        change_from_prior_close_percent=Decimal("12.0"),
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


def test_project_strategy_row_marks_building_state_for_valid_non_triggered_setup() -> None:
    projection = project_strategy_row(
        _row(),
        context_features=_features(),
        setup_validity=SetupValidity(
            setup_valid=True,
            evaluated_at=datetime(2026, 3, 14, 13, 40, tzinfo=UTC),
            first_catalyst_at=datetime(2026, 3, 14, 13, 0, tzinfo=UTC),
            catalyst_age_seconds=2400.0,
        ),
    )

    assert projection.stage_tag is StrategyStageTag.BUILDING
    assert projection.primary_invalid_reason is None
    assert any(reason.startswith("move=") for reason in projection.supporting_reasons)


def test_project_strategy_row_marks_trigger_ready_after_first_break_trigger() -> None:
    projection = project_strategy_row(
        _row(),
        context_features=_features(pullback_volume_lighter=True),
        setup_validity=SetupValidity(
            setup_valid=True,
            evaluated_at=datetime(2026, 3, 14, 13, 40, tzinfo=UTC),
            first_catalyst_at=datetime(2026, 3, 14, 13, 0, tzinfo=UTC),
            catalyst_age_seconds=2400.0,
        ),
        trigger_evaluation=TriggerEvaluation(
            triggered=True,
            interval_seconds=15,
            used_fallback=False,
            trigger_price=Decimal("24.10"),
            trigger_bar_started_at=datetime(2026, 3, 14, 13, 40, tzinfo=UTC),
            bullish_confirmation=True,
        ),
    )

    assert projection.stage_tag is StrategyStageTag.TRIGGER_READY
    assert "trigger=15s" in projection.supporting_reasons
    assert "bullish_confirmation" in projection.supporting_reasons
    assert "lighter_pullback_volume" in projection.supporting_reasons


def test_project_strategy_row_marks_invalidated_and_keeps_primary_invalid_reason() -> None:
    projection = project_strategy_row(
        _row(),
        context_features=_features(),
        setup_validity=SetupValidity(
            setup_valid=False,
            evaluated_at=datetime(2026, 3, 14, 13, 40, tzinfo=UTC),
            first_catalyst_at=datetime(2026, 3, 14, 13, 0, tzinfo=UTC),
            catalyst_age_seconds=2400.0,
            primary_invalid_reason=InvalidReason.STALE_CATALYST,
        ),
        invalidation=InvalidationDecision(True, TriggerInvalidationReason.SETUP_INVALID),
    )

    assert projection.stage_tag is StrategyStageTag.INVALIDATED
    # Specific setup reason ("stale_catalyst") takes priority over generic
    # invalidation wrapper ("setup_invalid") so the dashboard shows WHY.
    assert projection.primary_invalid_reason == InvalidReason.STALE_CATALYST.value
    assert projection.supporting_reasons == ("invalid=setup_invalid",)
