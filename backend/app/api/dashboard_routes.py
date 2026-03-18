from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from html import escape
from urllib.parse import parse_qs

from app.audit.pnl_summary import PnlSummary
from app.audit.review_models import TradeReviewFeed
from app.dashboard.renderers import render_dashboard_page
from app.ops.incident_log import IncidentLogReport
from app.ops.monitoring_models import OperationsOverview

from .dashboard_auth import DashboardAuthSettings, DashboardSessionManager
from .dashboard_models import DashboardOverviewModel, DashboardPageModel
from .dashboard_runtime import DashboardRuntimeSnapshotProvider


@dataclass(frozen=True, slots=True)
class DashboardHttpResponse:
    status_code: int
    body: bytes
    content_type: bytes = b"text/html; charset=utf-8"
    headers: tuple[tuple[bytes, bytes], ...] = field(default_factory=tuple)


class DashboardRoutes:
    overview_path = "/dashboard"
    login_path = "/dashboard/login"
    logs_path = "/dashboard/logs"
    trade_review_path = "/dashboard/trades"
    pnl_path = "/dashboard/pnl"

    def __init__(
        self,
        *,
        snapshot_provider: DashboardRuntimeSnapshotProvider | None = None,
        auth_settings: DashboardAuthSettings | None = None,
    ) -> None:
        self.snapshot_provider = snapshot_provider or DashboardRuntimeSnapshotProvider()
        self.sessions = DashboardSessionManager(auth_settings)

    def handles_path(self, path: str) -> bool:
        return path == "/" or path == self.overview_path or path.startswith(f"{self.overview_path}/")

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

    def render_section_page(
        self,
        snapshot,
        *,
        active_section: str,
    ) -> str:
        return render_dashboard_page(
            DashboardPageModel(
                overview=self.build_overview_model(snapshot.overview, snapshot.incident_report),
                active_section=active_section,
                last_updated_at=snapshot.last_updated_at,
                refresh_interval_seconds=snapshot.refresh_interval_seconds,
                stale=snapshot.stale,
                stale_message=snapshot.stale_message,
                review_feed=snapshot.review_feed,
                pnl_summary=snapshot.pnl_summary,
            )
        )

    def handle_http_request(
        self,
        *,
        method: str,
        path: str,
        headers: Iterable[tuple[bytes, bytes]],
        body: bytes,
    ) -> DashboardHttpResponse:
        if path == "/":
            return self._redirect(self.overview_path)
        if path == self.login_path:
            return self._handle_login(method=method, body=body)
        section = self._section_for_path(path)
        if section is None:
            return self._html_response(
                status_code=404,
                body=(
                    "<!DOCTYPE html><html lang='en'><body>"
                    "<h1>Dashboard route not found</h1>"
                    "<p>Return to the overview-first dashboard route.</p>"
                    f"<p><a href='{self.overview_path}'>Back to dashboard</a></p>"
                    "</body></html>"
                ),
            )
        if method.upper() != "GET":
            return self._html_response(
                status_code=405,
                body="<!DOCTYPE html><html lang='en'><body><h1>Method not allowed</h1></body></html>",
            )
        if not self.sessions.settings.configured:
            return self._html_response(
                status_code=503,
                body=(
                    "<!DOCTYPE html><html lang='en'><body>"
                    "<h1>Dashboard access unavailable</h1>"
                    "<p>Dashboard access is not configured.</p>"
                    "</body></html>"
                ),
            )
        if not self.sessions.is_authenticated(headers):
            return self._html_response(status_code=401, body=self._render_login_page())
        try:
            snapshot = self.snapshot_provider.build_snapshot()
        except Exception:
            return self._html_response(
                status_code=503,
                body=(
                    "<!DOCTYPE html><html lang='en'><body>"
                    "<h1>Dashboard refresh unavailable</h1>"
                    "<p>No successful dashboard snapshot is available yet.</p>"
                    "</body></html>"
                ),
            )
        return self._html_response(
            status_code=200,
            body=self.render_section_page(snapshot, active_section=section),
        )

    def _handle_login(
        self,
        *,
        method: str,
        body: bytes,
    ) -> DashboardHttpResponse:
        if not self.sessions.settings.configured:
            return self._html_response(
                status_code=503,
                body=(
                    "<!DOCTYPE html><html lang='en'><body>"
                    "<h1>Dashboard access unavailable</h1>"
                    "<p>Dashboard access is not configured.</p>"
                    "</body></html>"
                ),
            )
        if method.upper() != "POST":
            return self._html_response(status_code=200, body=self._render_login_page())

        submitted_password = parse_qs(body.decode("utf-8")).get("password", [""])[0]
        if not self.sessions.authenticate(submitted_password):
            return self._html_response(
                status_code=403,
                body=self._render_login_page(error_message="Password not accepted."),
            )
        return self._redirect(
            self.overview_path,
            headers=((b"set-cookie", self.sessions.session_cookie().encode("utf-8")),),
        )

    def _render_login_page(self, *, error_message: str | None = None) -> str:
        error_html = f"<p>{escape(error_message)}</p>" if error_message is not None else ""
        return (
            "<!DOCTYPE html><html lang='en'><body>"
            "<h1>Dashboard sign in</h1>"
            "<p>Read-only dashboard access requires the configured password.</p>"
            f"{error_html}"
            f"<form method='post' action='{self.login_path}'>"
            "<label>Password <input type='password' name='password' /></label>"
            "<button type='submit'>Sign in</button>"
            "</form>"
            "</body></html>"
        )

    def _section_for_path(self, path: str) -> str | None:
        if path == self.overview_path:
            return "overview"
        if path == self.logs_path:
            return "logs"
        if path == self.trade_review_path:
            return "trade-review"
        if path == self.pnl_path:
            return "pnl"
        return None

    def _html_response(
        self,
        *,
        status_code: int,
        body: str,
        headers: tuple[tuple[bytes, bytes], ...] = (),
    ) -> DashboardHttpResponse:
        return DashboardHttpResponse(
            status_code=status_code,
            body=body.encode("utf-8"),
            headers=headers,
        )

    def _redirect(
        self,
        location: str,
        *,
        headers: tuple[tuple[bytes, bytes], ...] = (),
    ) -> DashboardHttpResponse:
        return DashboardHttpResponse(
            status_code=303,
            body=b"",
            headers=((b"location", location.encode("utf-8")),) + headers,
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
                active_section="all",
                review_feed=review_feed,
                pnl_summary=pnl_summary,
            )
        )
