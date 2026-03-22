from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.api.dashboard_runtime import (
    DashboardRuntimeComposition,
    DashboardRuntimeSnapshot,
    DashboardRuntimeSnapshotProvider,
    create_default_dashboard_runtime,
    reset_default_dashboard_runtime,
)
from app.alerts.approval_workflow import approve_with_defaults, close_trade, record_entry_decision, record_pre_entry_alert
from app.alerts.models import PreEntryAlertState, TradeProposal, project_pre_entry_alert
from app.ops.alert_delivery_health import AlertDeliveryAttempt, AlertDeliveryResult
from app.audit.pnl_summary import PnlSummaryService
from app.audit.review_service import TradeReviewService
from app.ops.monitoring_models import ScannerLoopSnapshot
from app.ops.health_models import SystemTrustSnapshot, SystemTrustState
from app.ops.incident_log import IncidentLogService
from app.ops.overview_service import OperationsOverviewService
from app.ops.system_events import SystemEvent, SystemEventType
from app.paper.broker import PaperBroker
from app.providers.models import CatalystTag
from app.runtime.session_window import RuntimeWindow
from app.scanner.models import CandidateRow
from app.scanner.strategy_models import SetupValidity
from app.scanner.strategy_projection import StrategyProjection
from app.scanner.strategy_tags import StrategyStageTag
from app.scanner.trigger_logic import TriggerEvaluation
from decimal import Decimal


def test_snapshot_provider_returns_fresh_snapshot_when_factory_succeeds() -> None:
    snapshot = _runtime_snapshot()
    provider = DashboardRuntimeSnapshotProvider(snapshot_factory=lambda: snapshot)

    current = provider.build_snapshot()

    assert current.last_updated_at == snapshot.last_updated_at
    assert current.refresh_interval_seconds == 30
    assert current.stale is False
    assert current.stale_message is None


def test_snapshot_provider_reuses_last_successful_snapshot_when_refresh_fails() -> None:
    first_snapshot = _runtime_snapshot()
    calls = {"count": 0}

    def snapshot_factory() -> DashboardRuntimeSnapshot:
        calls["count"] += 1
        if calls["count"] == 1:
            return first_snapshot
        raise RuntimeError("runtime unavailable")

    provider = DashboardRuntimeSnapshotProvider(snapshot_factory=snapshot_factory)

    initial = provider.build_snapshot()
    fallback = provider.build_snapshot()

    assert initial.stale is False
    assert fallback.stale is True
    assert fallback.last_updated_at == first_snapshot.last_updated_at
    assert fallback.stale_message == "Showing the last successful snapshot while runtime refresh is unavailable."


def test_snapshot_provider_raises_when_no_successful_snapshot_exists() -> None:
    provider = DashboardRuntimeSnapshotProvider(
        snapshot_factory=lambda: (_ for _ in ()).throw(RuntimeError("no snapshot"))
    )

    with pytest.raises(RuntimeError, match="no snapshot"):
        provider.build_snapshot()


def test_default_dashboard_runtime_composition_owns_snapshot_dependencies() -> None:
    runtime = reset_default_dashboard_runtime()

    assert isinstance(runtime, DashboardRuntimeComposition)
    assert runtime.lifecycle_log.all_events() == ()

    snapshot = runtime.build_snapshot()

    assert snapshot.review_feed.total_trades == 0
    assert snapshot.pnl_summary.cumulative_trade_count == 0
    assert snapshot.incident_report.recent_critical_issues == ()
    assert snapshot.refresh_interval_seconds == 30


def test_create_default_dashboard_runtime_returns_shared_runtime_sources() -> None:
    first = reset_default_dashboard_runtime()
    second = create_default_dashboard_runtime()

    assert second is first


def test_default_runtime_snapshot_builds_from_shared_monitoring_and_lifecycle_sources() -> None:
    runtime = reset_default_dashboard_runtime()
    observed_at = datetime(2026, 3, 18, 10, 30, tzinfo=UTC)
    runtime_state = RuntimeWindow().status_at(observed_at)
    runtime.replace_trust_snapshot(
        SystemTrustSnapshot(
            observed_at=observed_at,
            trust_state=SystemTrustState.DEGRADED,
            actionable=False,
            runtime_state=runtime_state,
            provider_statuses=(),
            reasons=("polygon:market_data:stale_provider_update",),
        )
    )
    runtime.set_scanner_loop(
        ScannerLoopSnapshot(
            observed_at=observed_at,
            last_success_at=observed_at,
        )
    )
    runtime.record_system_event(
        SystemEvent(
            event_type=SystemEventType.PROVIDER_TRUST_DEGRADED,
            observed_at=observed_at,
            trust_state=SystemTrustState.DEGRADED,
            actionable=False,
            reasons=("polygon:market_data:stale_provider_update",),
        )
    )
    runtime.record_alert_delivery_attempts(
        (
            AlertDeliveryAttempt(
                occurred_at=observed_at,
                symbol="AKRX",
                alert_id="akrx-alert",
                result=AlertDeliveryResult.FAILURE,
                reason="telegram_timeout",
            ),
        )
    )
    _record_closed_trade(runtime, trade_id="runtime-trade-1", surfaced_at=observed_at)

    snapshot = runtime.build_snapshot()

    assert snapshot.overview.status.value == "degraded"
    assert {incident.source for incident in snapshot.incident_report.recent_critical_issues} == {
        "alert_delivery",
        "system_trust",
    }
    assert snapshot.review_feed.total_trades == 1
    assert snapshot.review_feed.days[0].trades[0].trade_id == "runtime-trade-1"
    assert snapshot.pnl_summary.cumulative_trade_count == 1


def _runtime_snapshot() -> DashboardRuntimeSnapshot:
    observed_at = datetime(2026, 3, 18, 10, 30, tzinfo=UTC)
    runtime_state = RuntimeWindow().status_at(observed_at)
    trust_snapshot = SystemTrustSnapshot(
        observed_at=observed_at,
        trust_state=SystemTrustState.HEALTHY,
        actionable=runtime_state.scanning_active,
        runtime_state=runtime_state,
        provider_statuses=(),
        reasons=(),
    )
    return DashboardRuntimeSnapshot(
        overview=OperationsOverviewService().build_overview(trust_snapshot),
        incident_report=IncidentLogService().build(()),
        review_feed=TradeReviewService().build_completed_trade_feed(()),
        pnl_summary=PnlSummaryService().build((), today=observed_at),
        last_updated_at=observed_at,
    )


def _record_closed_trade(
    runtime: DashboardRuntimeComposition,
    *,
    trade_id: str,
    surfaced_at: datetime,
) -> None:
    broker = PaperBroker()
    alert = _actionable_alert(surfaced_at=surfaced_at)
    record_pre_entry_alert(runtime.lifecycle_log, alert)
    decision = approve_with_defaults(alert, decided_at=surfaced_at)
    record_entry_decision(runtime.lifecycle_log, decision)
    trade = broker.open_trade(
        decision,
        trade_id=trade_id,
        quantity=100,
        lifecycle_log=runtime.lifecycle_log,
    )
    broker.apply_open_trade_command(
        trade,
        close_trade(trade.open_snapshot, decided_at=trade.opened_at),
        close_price="12.90",
        lifecycle_log=runtime.lifecycle_log,
    )


def _actionable_alert(*, surfaced_at: datetime):
    row = CandidateRow(
        symbol="AKRX",
        headline="AKRX reclaims VWAP after fresh news",
        catalyst_tag=CatalystTag.BREAKING_NEWS,
        latest_news_at=surfaced_at,
        time_since_news_seconds=90.0,
        observed_at=surfaced_at,
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
        surfaced_at=surfaced_at,
    )
