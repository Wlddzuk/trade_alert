from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import aiohttp
import yfinance as yf

from app.alerts.action_execution import TelegramActionExecutor
from app.alerts.action_resolution import TelegramActionRegistry
from app.alerts.alert_emission import TelegramAlertEmissionService
from app.alerts.delivery_state import TelegramDeliveryState
from app.alerts.telegram_runtime import TelegramRuntimeDeliveryService
from app.alerts.telegram_transport import TelegramTransport
from app.api import (
    DashboardAuthSettings,
    DashboardRoutes,
    DashboardRuntimeSnapshotProvider,
    TelegramCallbackHandler,
    TelegramRoutes,
)
from app.api.dashboard_runtime import DashboardRuntimeComposition, create_default_dashboard_runtime
from app.audit.lifecycle_log import LifecycleLog
from app.config import AppConfig
from app.ops.health_models import SystemTrustSnapshot, SystemTrustState
from app.ops.monitoring_models import ScannerLoopSnapshot
from app.paper.broker import PaperBroker
from app.runtime.session_window import RuntimeWindow
from app.scanner.feed_service import CandidateFeedService
from app.scanner.row_builder import build_candidate_row
from app.scanner.metrics import build_market_metrics
from app.scanner.news_linking import latest_news_by_symbol
from app.scanner.context_features import build_context_features
from app.scanner.invalidation import evaluate_invalidation
from app.scanner.setup_validity import evaluate_setup_validity
from app.scanner.strategy_projection import project_strategy_row
from app.scanner.trigger_logic import evaluate_first_break_trigger
from app.scanner.trigger_policy import resolve_trigger_bars


class BuySignalApp:
    def __init__(
        self,
        *,
        dashboard: DashboardRoutes | None = None,
        telegram: TelegramRoutes | None = None,
    ) -> None:
        self.dashboard = dashboard or DashboardRoutes()
        self.telegram = telegram or TelegramRoutes()

    async def __call__(
        self,
        scope: dict[str, object],
        receive: Callable[[], Awaitable[dict[str, object]]],
        send: Callable[[dict[str, object]], Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http":
            await _send_bytes(
                send,
                status_code=500,
                body=json.dumps(
                    {
                        "ok": False,
                        "status": "unsupported",
                        "message": "BuySignalApp only supports HTTP scopes.",
                    }
                ).encode("utf-8"),
                content_type=b"application/json",
            )
            return

        body = await _read_http_body(receive)
        method = str(scope.get("method", "GET"))
        path = str(scope.get("path", ""))
        headers = tuple(scope.get("headers", ()))
        if self.dashboard.handles_path(path):
            response = self.dashboard.handle_http_request(
                method=method,
                path=path,
                headers=headers,
                body=body,
            )
            await _send_bytes(
                send,
                status_code=response.status_code,
                body=response.body,
                content_type=response.content_type,
                headers=response.headers,
            )
            return

        response = self.telegram.handle_http_request(method=method, path=path, body=body)
        await _send_json(send, status_code=response.status_code, body=response.body)


def create_app(
    *,
    dashboard: DashboardRoutes | None = None,
    dashboard_runtime: DashboardRuntimeComposition | None = None,
    dashboard_snapshot_provider: DashboardRuntimeSnapshotProvider | None = None,
    dashboard_auth_settings: DashboardAuthSettings | None = None,
    app_config: AppConfig | None = None,
    telegram: TelegramRoutes | None = None,
) -> BuySignalApp:
    config = app_config or AppConfig.from_env()
    composed_dashboard_runtime = dashboard_runtime or create_default_dashboard_runtime()
    return BuySignalApp(
        dashboard=dashboard
        or DashboardRoutes(
            snapshot_provider=dashboard_snapshot_provider or composed_dashboard_runtime.snapshot_provider(),
            auth_settings=dashboard_auth_settings
            or DashboardAuthSettings(
                password=config.dashboard_password,
                session_secret=config.dashboard_session_secret,
                session_cookie_name=config.dashboard_session_cookie_name,
            ),
        ),
        telegram=telegram,
    )


@dataclass(frozen=True, slots=True)
class TelegramOperatorRuntime:
    app: BuySignalApp
    telegram_routes: TelegramRoutes
    callback_handler: TelegramCallbackHandler
    executor: TelegramActionExecutor
    registry: TelegramActionRegistry
    lifecycle_log: LifecycleLog
    delivery_state: TelegramDeliveryState
    delivery_service: TelegramRuntimeDeliveryService
    emission_service: TelegramAlertEmissionService
    feed_service: CandidateFeedService


def create_telegram_operator_runtime(
    *,
    transport: TelegramTransport,
    operator_chat_id: str,
    registry: TelegramActionRegistry | None = None,
    dashboard_runtime: DashboardRuntimeComposition | None = None,
    lifecycle_log: LifecycleLog | None = None,
    delivery_state: TelegramDeliveryState | None = None,
    broker: PaperBroker | None = None,
    entry_quantity: int = 50,
) -> TelegramOperatorRuntime:
    registry = registry or TelegramActionRegistry()
    dashboard_runtime = dashboard_runtime or DashboardRuntimeComposition()
    lifecycle_log = lifecycle_log or dashboard_runtime.lifecycle_log
    delivery_state = delivery_state or TelegramDeliveryState()
    delivery_service = TelegramRuntimeDeliveryService(transport)
    emission_service = TelegramAlertEmissionService(
        delivery_state=delivery_state,
        delivery_service=delivery_service,
        registry=registry,
        operator_chat_id=operator_chat_id,
        lifecycle_log=lifecycle_log,
        delivery_attempt_recorder=dashboard_runtime.record_alert_delivery_attempts,
    )
    feed_service = CandidateFeedService(qualifying_alert_emitter=emission_service)
    executor = TelegramActionExecutor(
        registry=registry,
        broker=broker or PaperBroker(),
        lifecycle_log=lifecycle_log,
        trade_id_factory=lambda alert_id: f"paper-{alert_id}",
        entry_quantity=entry_quantity,
    )
    callback_handler = TelegramCallbackHandler(executor=executor)
    telegram_routes = TelegramRoutes(callback_handler=callback_handler)
    app = create_app(telegram=telegram_routes, dashboard_runtime=dashboard_runtime)
    return TelegramOperatorRuntime(
        app=app,
        telegram_routes=telegram_routes,
        callback_handler=callback_handler,
        executor=executor,
        registry=registry,
        lifecycle_log=lifecycle_log,
        delivery_state=delivery_state,
        delivery_service=delivery_service,
        emission_service=emission_service,
        feed_service=feed_service,
    )


# ── Built-in scanner loop (lifespan background task) ─────────────────────────

_SCAN_SEED = [
    "AAPL","TSLA","NVDA","AMD","META","AMZN","MSFT","GOOGL","NFLX",
    "COIN","SOUN","MARA","RIOT","PLTR","SOFI","NIO","RIVN","SMCI",
    "ARM","HOOD","RBLX","SNAP","UBER","CRWD","APLD","IONQ",
    "INTC","MU","NET","SHOP","TSM","ADBE","PATH",
]
_SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL_SEC", "60"))
FINNHUB_BASE = "https://finnhub.io/api/v1"


def _bz_xml_to_dicts(raw: bytes) -> list:
    """Parse Benzinga XML into dicts matching BenzingaNewsProvider's expected shape."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(raw)
    results = []
    for item in root.findall("item"):
        stocks = []
        se = item.find("stocks")
        if se is not None:
            for s in se.findall("item"):
                n = s.find("name")
                if n is not None and (n.text or "").strip():
                    stocks.append({"name": n.text.strip()})
        channels = []
        ce = item.find("channels")
        if ce is not None:
            for c in ce.findall("item"):
                n = c.find("name")
                if n is not None and (n.text or "").strip():
                    channels.append({"name": n.text.strip()})
        results.append({
            "id":      (item.findtext("id") or "").strip(),
            "author":  (item.findtext("author") or "").strip(),
            "created": (item.findtext("created") or "").strip(),
            "updated": (item.findtext("updated") or "").strip(),
            "title":   (item.findtext("title") or "").strip(),
            "body":    (item.findtext("body") or "").strip() or None,
            "url":     (item.findtext("url") or "").strip() or None,
            "stocks":  stocks,
            "channels": channels,
        })
    return results


async def _scanner_loop(
    feed_service: CandidateFeedService,
    dashboard_runtime: DashboardRuntimeComposition,
    config: AppConfig,
) -> None:
    """Background scanner loop — runs inside the uvicorn process."""
    from app.providers.benzinga_adapter import BenzingaNewsProvider
    from app.providers.polygon_adapter import PolygonSnapshotProvider

    finnhub_key = os.environ.get("FINNHUB_API_KEY", "")

    def make_poly_fetch(session):
        async def fetch(url, params):
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as r:
                r.raise_for_status()
                return await r.json(content_type=None)
        return fetch

    def make_bz_fetch(session):
        async def fetch(url, params):
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as r:
                r.raise_for_status()
                return _bz_xml_to_dicts(await r.read())
        return fetch

    async def finnhub_quote(session, symbol):
        try:
            async with session.get(
                f"{FINNHUB_BASE}/quote",
                params={"symbol": symbol, "token": finnhub_key},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status != 200:
                    return symbol, None
                d = await r.json()
                return symbol, d if d.get("c") else None
        except Exception:
            return symbol, None

    async with aiohttp.ClientSession() as session:
        polygon  = PolygonSnapshotProvider(config.polygon,  fetch_json=make_poly_fetch(session))
        benzinga = BenzingaNewsProvider(config.benzinga, fetch_json=make_bz_fetch(session))

        while True:
            now = datetime.now(UTC)
            scan_start = now
            try:
                # 1. Benzinga news
                news_batch  = await benzinga.fetch_recent_news(_SCAN_SEED, limit=100)
                news_map    = latest_news_by_symbol(news_batch.records)
                active_syms = list(news_map.keys())[:40]

                if not active_syms:
                    await asyncio.sleep(_SCAN_INTERVAL)
                    continue

                # 2. Finnhub quotes
                quote_results = await asyncio.gather(
                    *[finnhub_quote(session, sym) for sym in active_syms]
                )
                from app.providers.models import MarketSnapshot
                snapshots = {}
                for sym, q in quote_results:
                    if not q:
                        continue
                    try:
                        snap = MarketSnapshot(
                            symbol=sym, provider="finnhub",
                            observed_at=datetime.fromtimestamp(q["t"], tz=UTC) if q.get("t") else now,
                            received_at=now,
                            last_price=str(q["c"]),
                            session_volume=0,
                            previous_close=str(q["pc"]) if q.get("pc") else None,
                            open_price=str(q["o"]) if q.get("o") else None,
                            high_price=str(q["h"]) if q.get("h") else None,
                            low_price=str(q["l"]) if q.get("l") else None,
                        )
                        snapshots[sym] = snap
                    except Exception:
                        continue

                # 3. Polygon daily bars (RVOL history)
                daily_bars = ()
                try:
                    db = await polygon.fetch_daily_bars(active_syms, lookback_days=20)
                    daily_bars = db.records
                except Exception:
                    pass

                # 4. yfinance intraday bars (EMA context) — run in thread
                loop = asyncio.get_event_loop()
                def _yf_bars():
                    import math
                    from app.providers.models import IntradayBar
                    try:
                        raw = yf.download(" ".join(active_syms), period="2d",
                                          interval="1m", progress=False, group_by="ticker")
                    except Exception:
                        return {}
                    result = {}
                    for sym in active_syms:
                        try:
                            df = raw if len(active_syms) == 1 else (
                                raw[sym] if sym in raw.columns.get_level_values(0) else None
                            )
                            if df is None or df.empty:
                                continue
                            if hasattr(df.columns, "levels"):
                                df.columns = df.columns.get_level_values(-1)
                            bars = []
                            for ts, row in df.iterrows():
                                try:
                                    bars.append(IntradayBar(
                                        symbol=sym, provider="yfinance",
                                        start_at=ts.to_pydatetime().astimezone(UTC),
                                        open_price=str(row["Open"]) if not math.isnan(float(row["Open"])) else "0",
                                        high_price=str(row["High"]) if not math.isnan(float(row["High"])) else "0",
                                        low_price=str(row["Low"]) if not math.isnan(float(row["Low"])) else "0",
                                        close_price=str(row["Close"]) if not math.isnan(float(row["Close"])) else "0",
                                        volume=int(row["Volume"]) if not math.isnan(float(row["Volume"])) else 0,
                                        interval_minutes=1,
                                    ))
                                except Exception:
                                    continue
                            if bars:
                                result[sym] = tuple(bars)
                        except Exception:
                            continue
                    return result
                intraday_by_sym = await loop.run_in_executor(None, _yf_bars)

                # 5. Build CandidateRows via full signal chain
                candidate_rows = []
                for sym in active_syms:
                    linked_news = news_map.get(sym)
                    snapshot    = snapshots.get(sym)
                    if not linked_news or not snapshot:
                        continue
                    metrics = build_market_metrics(
                        snapshot, daily_bars=daily_bars,
                        current_bar=None, historical_intraday_bars=(),
                        lookback_days=20,
                    )
                    row = build_candidate_row(snapshot, linked_news, metrics)
                    if row is None:
                        continue
                    intraday = intraday_by_sym.get(sym, ())
                    context     = build_context_features(snapshot, intraday_bars=intraday)
                    validity    = evaluate_setup_validity(row, linked_news, context)

                    # Trigger: preferred=15s (no 15s bars yet), fallback=60s (yfinance 1m)
                    trigger_sel  = resolve_trigger_bars(preferred_bars=(), fallback_bars=intraday)
                    trigger      = evaluate_first_break_trigger(trigger_sel)

                    # Invalidation gate
                    invalidation = evaluate_invalidation(
                        row, linked_news, context, setup_validity=validity
                    )

                    proj = project_strategy_row(
                        row,
                        context_features=context,
                        setup_validity=validity,
                        trigger_evaluation=trigger,
                        invalidation=invalidation,
                    )
                    candidate_rows.append(row)

                # 6. Push to dashboard
                runtime_state = RuntimeWindow().status_at(now)
                trust = SystemTrustSnapshot(
                    observed_at=now,
                    trust_state=SystemTrustState.HEALTHY,
                    actionable=runtime_state.scanning_active,
                    runtime_state=runtime_state,
                    provider_statuses=(),
                    reasons=(),
                )
                feed_snapshot = feed_service.refresh(candidate_rows, trust_snapshot=trust)

                # Update scanner loop status on dashboard
                scanner_snap = ScannerLoopSnapshot(
                    observed_at=now,
                    last_success_at=now,
                )
                dashboard_runtime.set_scanner_loop(scanner_snap)
                dashboard_runtime.replace_trust_snapshot(trust)

            except Exception as exc:
                scanner_snap = ScannerLoopSnapshot(
                    observed_at=now,
                    last_success_at=None,
                    last_error=str(exc)[:200],
                )
                dashboard_runtime.set_scanner_loop(scanner_snap)

            await asyncio.sleep(_SCAN_INTERVAL)


# ── Shared state: scanner loop + HTTP dashboard read from the same runtime ────

_shared_dashboard_runtime = create_default_dashboard_runtime()
_shared_feed_service = CandidateFeedService()
_http_app = create_app(dashboard_runtime=_shared_dashboard_runtime)
_scanner_task: asyncio.Task | None = None


async def _lifespan(scope, receive, send) -> None:
    """ASGI lifespan handler — starts scanner background task on startup."""
    global _scanner_task
    event = await receive()
    if event["type"] == "lifespan.startup":
        config = AppConfig.from_env()
        _scanner_task = asyncio.create_task(
            _scanner_loop(_shared_feed_service, _shared_dashboard_runtime, config)
        )
        await send({"type": "lifespan.startup.complete"})
    event = await receive()
    if event["type"] == "lifespan.shutdown":
        if _scanner_task and not _scanner_task.done():
            _scanner_task.cancel()
        await send({"type": "lifespan.shutdown.complete"})


async def app(scope, receive, send):
    """Top-level ASGI entrypoint dispatching lifespan and HTTP."""
    if scope["type"] == "lifespan":
        await _lifespan(scope, receive, send)
    else:
        await _http_app(scope, receive, send)


async def _read_http_body(
    receive: Callable[[], Awaitable[dict[str, object]]],
) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        body = message.get("body", b"")
        if isinstance(body, bytes):
            chunks.append(body)
        elif isinstance(body, bytearray):
            chunks.append(bytes(body))
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


async def _send_json(
    send: Callable[[dict[str, object]], Awaitable[None]],
    *,
    status_code: int,
    body: dict[str, object],
) -> None:
    encoded = json.dumps(body).encode("utf-8")
    await _send_bytes(
        send,
        status_code=status_code,
        body=encoded,
        content_type=b"application/json",
    )


async def _send_bytes(
    send: Callable[[dict[str, object]], Awaitable[None]],
    *,
    status_code: int,
    body: bytes,
    content_type: bytes,
    headers: tuple[tuple[bytes, bytes], ...] = (),
) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [(b"content-type", content_type), *headers],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": body,
            "more_body": False,
        }
    )
