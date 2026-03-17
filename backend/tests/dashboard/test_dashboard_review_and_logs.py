from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.alerts.approval_workflow import (
    adjust_trade_target,
    approve_with_defaults,
    close_trade,
    record_entry_decision,
    record_pre_entry_alert,
)
from app.alerts.models import PreEntryAlertState, TradeProposal, project_pre_entry_alert
from app.api.dashboard_routes import DashboardRoutes
from app.audit.lifecycle_log import LifecycleLog
from app.audit.pnl_summary import PnlSummaryService
from app.audit.review_service import TradeReviewService
from app.ops.degraded_state import SystemTrustMonitor
from app.ops.health_models import ProviderFreshnessRules, SystemTrustState
from app.ops.incident_log import IncidentLogService
from app.ops.monitoring_models import AlertDeliverySnapshot, ScannerLoopSnapshot
from app.ops.overview_service import OperationsOverviewService
from app.ops.provider_health import ProviderHealthEvaluator
from app.ops.system_events import SystemEvent, SystemEventType
from app.paper.broker import PaperBroker
from app.providers.models import CatalystTag, ProviderCapability, ProviderHealthSnapshot, ProviderHealthState
from app.runtime.session_window import RuntimeWindow
from app.scanner.models import CandidateRow
from app.scanner.strategy_models import SetupValidity
from app.scanner.strategy_projection import StrategyProjection
from app.scanner.strategy_tags import StrategyStageTag
from app.scanner.trigger_logic import TriggerEvaluation


def test_dashboard_sections_render_logs_review_and_pnl_without_controls() -> None:
    runtime_at = datetime(2026, 3, 17, 14, 0, tzinfo=UTC)
    overview = _build_overview(runtime_at)
    incident_report = IncidentLogService().build(
        (
            SystemEvent(
                event_type=SystemEventType.PROVIDER_TRUST_DEGRADED,
                observed_at=runtime_at - timedelta(minutes=8),
                trust_state=SystemTrustState.DEGRADED,
                actionable=False,
                reasons=("polygon:market_data:stale_provider_update",),
            ),
            SystemEvent(
                event_type=SystemEventType.PROVIDER_TRUST_RESTORED,
                observed_at=runtime_at - timedelta(minutes=2),
                trust_state=SystemTrustState.HEALTHY,
                actionable=True,
                reasons=("all_providers_fresh",),
            ),
        )
    )

    log = LifecycleLog()
    broker = PaperBroker()
    _record_closed_trade(log, broker, "dashboard-day-1", surfaced_at=datetime(2026, 3, 16, 14, 0, tzinfo=UTC), close_price="13.30")
    _record_closed_trade(log, broker, "dashboard-day-2", surfaced_at=datetime(2026, 3, 17, 14, 0, tzinfo=UTC), close_price="12.10")

    review_feed = TradeReviewService().build_completed_trade_feed(log.all_events())
    pnl_summary = PnlSummaryService().build(log.all_events(), today=date(2026, 3, 17))

    html = DashboardRoutes().render_dashboard_page(
        overview,
        incident_report,
        review_feed=review_feed,
        pnl_summary=pnl_summary,
    )

    assert "Logs" in html
    assert "Trade Review" in html
    assert "Paper P&amp;L" in html
    assert "Recent critical issues" in html
    assert "Recently resolved incidents" in html
    assert "2026-03-17" in html
    assert "2026-03-16" in html
    assert "Raw lifecycle events remain secondary detail." in html
    assert "Cumulative realized P&amp;L" in html
    assert "<button" not in html
    assert "<form" not in html
    assert "Approve" not in html
    assert "Close Trade" not in html


def _build_overview(runtime_at: datetime):
    runtime_state = RuntimeWindow().status_at(runtime_at)
    transition = SystemTrustMonitor().evaluate(
        (
            _provider_status("polygon", ProviderCapability.MARKET_DATA, runtime_at=runtime_at, freshness_age_seconds=5.0),
            _provider_status("benzinga", ProviderCapability.NEWS, runtime_at=runtime_at, freshness_age_seconds=12.0),
        ),
        runtime_state,
    )
    return OperationsOverviewService().build_overview(
        transition.snapshot,
        scanner_loop=ScannerLoopSnapshot(observed_at=runtime_at, last_success_at=runtime_at - timedelta(seconds=15)),
        alert_delivery=AlertDeliverySnapshot(
            observed_at=runtime_at,
            last_attempt_at=runtime_at - timedelta(seconds=4),
            last_success_at=runtime_at - timedelta(seconds=4),
            consecutive_failures=0,
        ),
    )


def _provider_status(
    provider: str,
    capability: ProviderCapability,
    *,
    runtime_at: datetime,
    freshness_age_seconds: float,
):
    runtime_state = RuntimeWindow().status_at(runtime_at)
    evaluator = ProviderHealthEvaluator(ProviderFreshnessRules())
    return evaluator.evaluate(
        ProviderHealthSnapshot(
            provider=provider,
            capability=capability,
            observed_at=runtime_state.observed_at_utc,
            last_update_at=runtime_state.observed_at_utc - timedelta(seconds=freshness_age_seconds),
            freshness_age_seconds=freshness_age_seconds,
            state=ProviderHealthState.HEALTHY,
            reason="test",
        ),
        runtime_state,
    )


def _record_closed_trade(
    log: LifecycleLog,
    broker: PaperBroker,
    trade_id: str,
    *,
    surfaced_at: datetime,
    close_price: str,
) -> None:
    alert = replace(_actionable_alert(), surfaced_at=surfaced_at, alert_id=None)
    record_pre_entry_alert(log, alert)
    decision = approve_with_defaults(alert, decided_at=surfaced_at + timedelta(seconds=5))
    record_entry_decision(log, decision)
    trade = broker.open_trade(decision, trade_id=trade_id, quantity=300, lifecycle_log=log)
    adjusted = broker.apply_open_trade_command(
        trade,
        adjust_trade_target(
            trade.open_snapshot,
            new_target_price="13.90",
            decided_at=trade.opened_at + timedelta(seconds=10),
        ),
        lifecycle_log=log,
    )
    broker.apply_open_trade_command(
        adjusted,
        close_trade(
            adjusted.open_snapshot,
            decided_at=adjusted.opened_at + timedelta(seconds=20),
        ),
        close_price=close_price,
        lifecycle_log=log,
    )


def _actionable_alert():
    observed_at = datetime(2026, 3, 15, 14, 40, tzinfo=UTC)
    row = CandidateRow(
        symbol="AKRX",
        headline="AKRX reclaims VWAP after fresh news",
        catalyst_tag=CatalystTag.BREAKING_NEWS,
        latest_news_at=observed_at,
        time_since_news_seconds=90.0,
        observed_at=observed_at,
        price=Decimal("12.45"),
        volume=2_100_000,
        average_daily_volume=Decimal("900000"),
        daily_relative_volume=Decimal("4.4"),
        short_term_relative_volume=Decimal("3.1"),
        gap_percent=Decimal("12.0"),
        change_from_prior_close_percent=Decimal("19.0"),
        pullback_from_high_percent=Decimal("4.8"),
        why_surfaced="breaking_news | move=19% | daily_rvol=4.4x",
    )
    projection = StrategyProjection(
        row=row,
        setup_validity=SetupValidity(
            setup_valid=True,
            evaluated_at=row.observed_at,
            first_catalyst_at=row.latest_news_at,
            catalyst_age_seconds=90.0,
        ),
        score=97,
        stage_tag=StrategyStageTag.TRIGGER_READY,
        supporting_reasons=("move=19%", "daily_rvol=4.4x", "trigger=15s"),
        primary_invalid_reason=None,
        trigger_evaluation=TriggerEvaluation(
            triggered=True,
            interval_seconds=15,
            used_fallback=False,
            trigger_price=Decimal("12.45"),
            trigger_bar_started_at=row.observed_at,
            bullish_confirmation=True,
        ),
        invalidation=None,
    )
    return project_pre_entry_alert(
        projection,
        TradeProposal(
            symbol="AKRX",
            entry_price="12.45",
            stop_price="11.95",
            target_price="13.60",
        ),
        state=PreEntryAlertState.ACTIONABLE,
        rank=1,
    )
