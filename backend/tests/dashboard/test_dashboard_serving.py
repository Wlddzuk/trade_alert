from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from app.api import DashboardAuthSettings, DashboardRuntimeSnapshotProvider
from app.api.dashboard_runtime import DashboardRuntimeSnapshot
from app.audit.pnl_summary import PnlSummaryService
from app.audit.review_service import TradeReviewService
from app.ops.health_models import SystemTrustSnapshot, SystemTrustState
from app.ops.incident_log import IncidentLogService
from app.ops.overview_service import OperationsOverviewService
from app.main import create_app
from app.runtime.session_window import RuntimeWindow


def test_dashboard_route_dispatch_preserves_telegram_webhook_behavior() -> None:
    app = create_app(
        dashboard_snapshot_provider=DashboardRuntimeSnapshotProvider(),
        dashboard_auth_settings=DashboardAuthSettings(password="swing", session_secret="phase-07"),
    )

    dashboard_status, dashboard_headers, dashboard_body = _request("GET", "/dashboard", app=app)
    assert dashboard_status == 401
    assert dashboard_headers["content-type"].startswith("text/html")
    assert "Dashboard sign in" in dashboard_body

    telegram_status, telegram_headers, telegram_body = _request(
        "POST",
        "/telegram/webhook",
        app=app,
        payload={},
    )
    assert telegram_status == 202
    assert telegram_headers["content-type"].startswith("application/json")
    assert telegram_body["status"] == "ignored"


def test_root_redirects_to_dashboard_overview() -> None:
    app = create_app(
        dashboard_snapshot_provider=DashboardRuntimeSnapshotProvider(),
        dashboard_auth_settings=DashboardAuthSettings(password="swing", session_secret="phase-07"),
    )

    status, headers, _ = _request("GET", "/", app=app)

    assert status == 303
    assert headers["location"] == "/dashboard"


def test_dashboard_not_found_returns_helpful_html_page() -> None:
    app = create_app(
        dashboard_snapshot_provider=DashboardRuntimeSnapshotProvider(),
        dashboard_auth_settings=DashboardAuthSettings(password="swing", session_secret="phase-07"),
    )

    status, headers, body = _request("GET", "/dashboard/mistyped", app=app)

    assert status == 404
    assert headers["content-type"].startswith("text/html")
    assert "Dashboard route not found" in body
    assert "Back to dashboard" in body


def test_dashboard_section_routes_render_read_only_review_flow() -> None:
    app = create_app(
        dashboard_snapshot_provider=DashboardRuntimeSnapshotProvider(
            snapshot_factory=lambda: _runtime_snapshot()
        ),
        dashboard_auth_settings=DashboardAuthSettings(password="swing", session_secret="phase-07"),
    )

    login_status, login_headers, _ = _request(
        "POST",
        "/dashboard/login",
        app=app,
        form={"password": "swing"},
    )
    assert login_status == 303
    cookie = login_headers["set-cookie"]

    logs_status, _, logs_body = _request("GET", "/dashboard/logs", app=app, cookie=cookie)
    trades_status, _, trades_body = _request("GET", "/dashboard/trades", app=app, cookie=cookie)
    pnl_status, _, pnl_body = _request("GET", "/dashboard/pnl", app=app, cookie=cookie)

    assert logs_status == 200
    assert "Logs" in logs_body
    assert "Last updated:" in logs_body
    assert "Auto-refresh: every 30 seconds" in logs_body

    assert trades_status == 200
    assert "Trade Review" in trades_body
    assert "collapsed day groups" in trades_body

    assert pnl_status == 200
    assert "Paper P&amp;L" in pnl_body
    assert "Read-only dashboard" in pnl_body


def test_default_app_serves_dashboard_after_config_backed_login(monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_PASSWORD", "swing")
    monkeypatch.setenv("DASHBOARD_SESSION_SECRET", "phase-10-session")
    app = create_app()

    login_status, login_headers, _ = _request(
        "POST",
        "/dashboard/login",
        app=app,
        form={"password": "swing"},
    )

    assert login_status == 303
    cookie = login_headers["set-cookie"]

    dashboard_status, _, dashboard_body = _request("GET", "/dashboard", app=app, cookie=cookie)

    assert dashboard_status == 200
    assert "Status Overview" in dashboard_body
    assert "Read-only dashboard" in dashboard_body


def test_dashboard_stale_snapshot_route_uses_last_successful_snapshot() -> None:
    snapshot = _runtime_snapshot()
    calls = {"count": 0}

    def snapshot_factory() -> DashboardRuntimeSnapshot:
        calls["count"] += 1
        if calls["count"] == 1:
            return snapshot
        raise RuntimeError("refresh failed")

    app = create_app(
        dashboard_snapshot_provider=DashboardRuntimeSnapshotProvider(snapshot_factory=snapshot_factory),
        dashboard_auth_settings=DashboardAuthSettings(password="swing", session_secret="phase-07"),
    )
    _, login_headers, _ = _request(
        "POST",
        "/dashboard/login",
        app=app,
        form={"password": "swing"},
    )
    cookie = login_headers["set-cookie"]

    first_status, _, first_body = _request("GET", "/dashboard", app=app, cookie=cookie)
    second_status, _, second_body = _request("GET", "/dashboard", app=app, cookie=cookie)

    assert first_status == 200
    assert "Stale warning:" not in first_body
    assert second_status == 200
    assert "Stale warning: Showing the last successful snapshot while runtime refresh is unavailable." in second_body
    assert snapshot.last_updated_at.isoformat() in second_body


def _request(
    method: str,
    path: str,
    *,
    app,
    payload: dict[str, object] | None = None,
    form: dict[str, str] | None = None,
    cookie: str | None = None,
) -> tuple[int, dict[str, str], str | dict[str, object]]:
    body = b""
    headers: tuple[tuple[bytes, bytes], ...] = ()
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers = ((b"content-type", b"application/json"),)
    if form is not None:
        body = "&".join(f"{key}={value}" for key, value in form.items()).encode("utf-8")
        headers = ((b"content-type", b"application/x-www-form-urlencoded"),)
    if cookie is not None:
        headers = (*headers, (b"cookie", cookie.encode("utf-8")))
    return asyncio.run(_asgi_request(app, method=method, path=path, body=body, headers=headers))


async def _asgi_request(
    app,
    *,
    method: str,
    path: str,
    body: bytes,
    headers: tuple[tuple[bytes, bytes], ...],
) -> tuple[int, dict[str, str], str | dict[str, object]]:
    sent: list[dict[str, object]] = []
    delivered = False

    async def receive() -> dict[str, object]:
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await app(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": list(headers),
        },
        receive,
        send,
    )

    start = next(message for message in sent if message["type"] == "http.response.start")
    response_headers = {
        key.decode("utf-8"): value.decode("utf-8")
        for key, value in start.get("headers", [])
    }
    response_body = next(message["body"] for message in sent if message["type"] == "http.response.body")
    if response_headers["content-type"].startswith("application/json"):
        return int(start["status"]), response_headers, json.loads(response_body.decode("utf-8"))
    return int(start["status"]), response_headers, response_body.decode("utf-8")


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
