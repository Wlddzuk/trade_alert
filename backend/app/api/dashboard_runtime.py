from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Callable

from app.audit.pnl_summary import PnlSummary, PnlSummaryService
from app.audit.review_models import TradeReviewFeed
from app.audit.review_service import TradeReviewService
from app.ops.health_models import SystemTrustSnapshot, SystemTrustState
from app.ops.incident_log import IncidentLogReport, IncidentLogService
from app.ops.monitoring_models import OperationsOverview
from app.ops.overview_service import OperationsOverviewService
from app.runtime.session_window import RuntimeWindow


@dataclass(frozen=True, slots=True)
class DashboardRuntimeSnapshot:
    overview: OperationsOverview
    incident_report: IncidentLogReport
    review_feed: TradeReviewFeed
    pnl_summary: PnlSummary
    last_updated_at: datetime
    refresh_interval_seconds: int = 30
    stale: bool = False
    stale_message: str | None = None


class DashboardRuntimeSnapshotProvider:
    def __init__(
        self,
        *,
        snapshot_factory: Callable[[], DashboardRuntimeSnapshot] | None = None,
    ) -> None:
        self._snapshot_factory = snapshot_factory or _build_default_snapshot
        self._last_successful_snapshot: DashboardRuntimeSnapshot | None = None

    def build_snapshot(self) -> DashboardRuntimeSnapshot:
        try:
            snapshot = self._snapshot_factory()
        except Exception:
            if self._last_successful_snapshot is None:
                raise
            return replace(
                self._last_successful_snapshot,
                stale=True,
                stale_message="Showing the last successful snapshot while runtime refresh is unavailable.",
            )
        self._last_successful_snapshot = snapshot
        return snapshot


def _build_default_snapshot() -> DashboardRuntimeSnapshot:
    observed_at = datetime.now(UTC)
    runtime_state = RuntimeWindow().status_at(observed_at)
    trust_snapshot = SystemTrustSnapshot(
        observed_at=observed_at,
        trust_state=SystemTrustState.HEALTHY,
        actionable=runtime_state.scanning_active,
        runtime_state=runtime_state,
        provider_statuses=(),
        reasons=(),
    )
    overview_service = OperationsOverviewService()
    return DashboardRuntimeSnapshot(
        overview=overview_service.build_overview(trust_snapshot),
        incident_report=IncidentLogService().build(()),
        review_feed=TradeReviewService().build_completed_trade_feed(()),
        pnl_summary=PnlSummaryService().build((), today=observed_at),
        last_updated_at=observed_at,
    )
