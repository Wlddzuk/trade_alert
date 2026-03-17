from __future__ import annotations

from app.audit.pnl_summary import PnlSummary
from app.audit.review_models import TradeReviewFeed
from app.dashboard.renderers import render_dashboard_page
from app.ops.incident_log import IncidentLogReport
from app.ops.monitoring_models import OperationsOverview

from .dashboard_models import DashboardOverviewModel, DashboardPageModel


class DashboardRoutes:
    def build_overview_model(
        self,
        overview: OperationsOverview,
        incident_report: IncidentLogReport,
    ) -> DashboardOverviewModel:
        return DashboardOverviewModel(
            read_only_label="Read-only dashboard",
            primary_workflow_label="Telegram remains the primary workflow.",
            overview=overview,
            incident_report=incident_report,
        )

    def render_overview_page(
        self,
        overview: OperationsOverview,
        incident_report: IncidentLogReport,
    ) -> str:
        return render_dashboard_page(
            DashboardPageModel(
                overview=self.build_overview_model(overview, incident_report),
            )
        )

    def render_dashboard_page(
        self,
        overview: OperationsOverview,
        incident_report: IncidentLogReport,
        *,
        review_feed: TradeReviewFeed,
        pnl_summary: PnlSummary,
    ) -> str:
        return render_dashboard_page(
            DashboardPageModel(
                overview=self.build_overview_model(overview, incident_report),
                review_feed=review_feed,
                pnl_summary=pnl_summary,
            )
        )
