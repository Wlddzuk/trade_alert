from __future__ import annotations

import asyncio
import pytest

from app.api import DashboardAuthSettings, DashboardRuntimeSnapshotProvider
from app.main import create_app


def test_dashboard_requires_configuration_and_fails_closed() -> None:
    status, headers, body = _request("GET", "/dashboard")

    assert status == 503
    assert headers["content-type"].startswith("text/html")
    assert "Dashboard access is not configured." in body


def test_dashboard_login_sets_session_cookie_and_reuses_browser_session_from_app_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHBOARD_PASSWORD", "swing")
    monkeypatch.setenv("DASHBOARD_SESSION_SECRET", "phase-10-session")
    app = create_app()

    denied_status, _, denied_body = _request("GET", "/dashboard", app=app)
    assert denied_status == 401
    assert "Dashboard sign in" in denied_body

    status, headers, _ = _request(
        "POST",
        "/dashboard/login",
        app=app,
        body="password=swing",
        headers=((b"content-type", b"application/x-www-form-urlencoded"),),
    )

    assert status == 303
    assert headers["location"] == "/dashboard"
    cookie = headers["set-cookie"]
    assert "buy_signal_dashboard_session=" in cookie

    authed_status, _, authed_body = _request(
        "GET",
        "/dashboard",
        app=app,
        headers=((b"cookie", cookie.encode("utf-8")),),
    )
    assert authed_status == 200
    assert "Status Overview" in authed_body


def test_dashboard_rejects_wrong_password() -> None:
    app = create_app(
        dashboard_snapshot_provider=DashboardRuntimeSnapshotProvider(),
        dashboard_auth_settings=DashboardAuthSettings(password="swing", session_secret="phase-07"),
    )

    status, _, body = _request(
        "POST",
        "/dashboard/login",
        app=app,
        body="password=wrong",
        headers=((b"content-type", b"application/x-www-form-urlencoded"),),
    )

    assert status == 403
    assert "Password not accepted." in body


def _request(
    method: str,
    path: str,
    *,
    app=None,
    body: str = "",
    headers: tuple[tuple[bytes, bytes], ...] = (),
) -> tuple[int, dict[str, str], str]:
    app = app or create_app()
    return asyncio.run(_asgi_request(app, method=method, path=path, body=body.encode("utf-8"), headers=headers))


async def _asgi_request(
    app,
    *,
    method: str,
    path: str,
    body: bytes,
    headers: tuple[tuple[bytes, bytes], ...],
) -> tuple[int, dict[str, str], str]:
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
    return int(start["status"]), response_headers, response_body.decode("utf-8")
