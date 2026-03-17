from __future__ import annotations

from dataclasses import dataclass

from app.audit.pnl_summary import PnlSummary
from app.audit.review_models import TradeReviewFeed
from app.ops.incident_log import IncidentLogReport
from app.ops.monitoring_models import OperationsOverview


@dataclass(frozen=True, slots=True)
class DashboardOverviewModel:
    read_only_label: str
    primary_workflow_label: str
    overview: OperationsOverview
    incident_report: IncidentLogReport


@dataclass(frozen=True, slots=True)
class DashboardPageModel:
    overview: DashboardOverviewModel
    review_feed: TradeReviewFeed | None = None
    pnl_summary: PnlSummary | None = None
