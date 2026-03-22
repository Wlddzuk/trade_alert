from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.api.dashboard_runtime import (
    DashboardRuntimeComposition,
    DashboardRuntimeSnapshot,
    DashboardRuntimeSnapshotProvider,
    create_default_dashboard_runtime,
)
from app.audit.pnl_summary import PnlSummaryService
from app.audit.review_service import TradeReviewService
from app.ops.health_models import SystemTrustSnapshot, SystemTrustState
from app.ops.incident_log import IncidentLogService
from app.ops.overview_service import OperationsOverviewService
from app.runtime.session_window import RuntimeWindow


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
    runtime = create_default_dashboard_runtime()

    assert isinstance(runtime, DashboardRuntimeComposition)
    assert runtime.lifecycle_log.all_events() == ()

    snapshot = runtime.build_snapshot()

    assert snapshot.review_feed.total_trades == 0
    assert snapshot.pnl_summary.cumulative_trade_count == 0
    assert snapshot.incident_report.recent_critical_issues == ()
    assert snapshot.refresh_interval_seconds == 30


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
