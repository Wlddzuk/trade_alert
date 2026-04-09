from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.alerts.models import PreEntryAlertState, TradeProposal, project_pre_entry_alert
from app.alerts.telegram_renderer import render_pre_entry_alert
from app.providers.models import CatalystTag
from app.scanner.models import CandidateRow
from app.scanner.strategy_models import InvalidReason, SetupValidity
from app.scanner.strategy_projection import StrategyProjection
from app.scanner.strategy_tags import StrategyStageTag
from app.scanner.trigger_logic import TriggerEvaluation


def _row() -> CandidateRow:
    observed_at = datetime(2026, 3, 15, 13, 40, tzinfo=UTC)
    return CandidateRow(
        symbol="akrx",
        headline="AKRX extends catalyst window",
        catalyst_tag=CatalystTag.BREAKING_NEWS,
        latest_news_at=observed_at,
        time_since_news_seconds=240.0,
        observed_at=observed_at,
        price=Decimal("12.40"),
        volume=1_250_000,
        average_daily_volume=Decimal("500000"),
        daily_relative_volume=Decimal("4.1"),
        short_term_relative_volume=Decimal("2.6"),
        gap_percent=Decimal("11.3"),
        change_from_prior_close_percent=Decimal("18.2"),
        pullback_from_high_percent=Decimal("5.1"),
        why_surfaced="breaking_news | move=18.2% | daily_rvol=4.1x",
    )


def _projection(*, stage_tag: StrategyStageTag, primary_invalid_reason: str | None = None) -> StrategyProjection:
    row = _row()
    trigger = None
    if stage_tag is StrategyStageTag.TRIGGER_READY:
        trigger = TriggerEvaluation(
            triggered=True,
            interval_seconds=15,
            used_fallback=False,
            trigger_price=Decimal("12.45"),
            trigger_bar_started_at=row.observed_at,
            bullish_confirmation=True,
        )

    return StrategyProjection(
        row=row,
        setup_validity=SetupValidity(
            setup_valid=stage_tag is not StrategyStageTag.INVALIDATED,
            evaluated_at=row.observed_at,
            first_catalyst_at=row.latest_news_at,
            catalyst_age_seconds=240.0,
            primary_invalid_reason=None,
        )
        if stage_tag is not StrategyStageTag.INVALIDATED
        else SetupValidity(
            setup_valid=False,
            evaluated_at=row.observed_at,
            first_catalyst_at=row.latest_news_at,
            catalyst_age_seconds=240.0,
            primary_invalid_reason=InvalidReason.STALE_CATALYST,
        ),
        score=94 if stage_tag is StrategyStageTag.TRIGGER_READY else 88,
        stage_tag=stage_tag,
        supporting_reasons=("move=18.2%", "daily_rvol=4.1x", "trigger=15s") if trigger else ("move=18.2%",),
        primary_invalid_reason=primary_invalid_reason,
        trigger_evaluation=trigger,
        invalidation=None,
    )


def _proposal() -> TradeProposal:
    return TradeProposal(
        symbol="AKRX",
        entry_price="12.45",
        stop_price="11.95",
        target_price="13.60",
        thesis="VWAP reclaim with fresh catalyst",
    )


def test_project_pre_entry_alert_creates_watch_alert_from_building_projection() -> None:
    alert = project_pre_entry_alert(
        _projection(stage_tag=StrategyStageTag.BUILDING),
        _proposal(),
        state=PreEntryAlertState.WATCH,
        rank=2,
    )

    assert alert.symbol == "AKRX"
    assert alert.approval_capable is False
    assert alert.alert_id.startswith("akrx-watch-")


def test_project_pre_entry_alert_requires_trigger_ready_for_actionable_alerts() -> None:
    with pytest.raises(ValueError, match="trigger-ready projection"):
        project_pre_entry_alert(
            _projection(stage_tag=StrategyStageTag.BUILDING),
            _proposal(),
            state=PreEntryAlertState.ACTIONABLE,
            rank=1,
        )


def test_rejected_alert_can_reuse_projection_invalid_reason() -> None:
    alert = project_pre_entry_alert(
        _projection(stage_tag=StrategyStageTag.INVALIDATED, primary_invalid_reason="stale_catalyst"),
        _proposal(),
        state=PreEntryAlertState.REJECTED,
        rank=4,
    )

    assert alert.display_reason == "stale_catalyst"


def test_render_pre_entry_alert_includes_context_levels_and_rank() -> None:
    alert = project_pre_entry_alert(
        _projection(stage_tag=StrategyStageTag.TRIGGER_READY),
        _proposal(),
        state=PreEntryAlertState.ACTIONABLE,
        rank=1,
    )

    rendered = render_pre_entry_alert(alert)

    assert "[Actionable] AKRX" in rendered.text
    assert "Catalyst: Breaking News" in rendered.text
    assert "Entry:    12.45" in rendered.text
    assert "Stop:     11.95" in rendered.text
    assert "Target:   13.6" in rendered.text
    assert "score 94/100" in rendered.text
    assert "trigger ready" in rendered.text
    assert "AKRX extends catalyst window" in rendered.text
    assert "move=18.2%, daily_rvol=4.1x, trigger=15s" in rendered.text
