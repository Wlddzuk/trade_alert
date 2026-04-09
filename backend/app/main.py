from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import aiohttp
import yfinance as yf

from app.alerts.action_execution import TelegramActionExecutor
from app.alerts.action_resolution import TelegramActionRegistry
from app.alerts.alert_emission import TelegramAlertEmissionService
from app.alerts.delivery_state import TelegramDeliveryState
from app.alerts.telegram_runtime import TelegramRuntimeDeliveryService
from app.alerts.http_telegram_transport import HttpTelegramTransport
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
from app.intelligence.sentiment_analyzer import SentimentAnalyzer
from app.intelligence.outcome_store import OutcomeStore
from app.intelligence.adaptive_scorer import AdaptiveScorer
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


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


def _next_market_open(now: datetime) -> datetime:
    """Return the next US market open (9:30 ET) from the given UTC time."""
    from zoneinfo import ZoneInfo
    et = now.astimezone(ZoneInfo("America/New_York"))
    market_open_time = et.replace(hour=9, minute=30, second=0, microsecond=0)
    # If it's before open today and a weekday, use today
    if et.weekday() < 5 and et < market_open_time:
        return market_open_time.astimezone(UTC)
    # Otherwise find next weekday
    candidate = et + timedelta(days=1)
    while candidate.weekday() >= 5:  # skip Sat/Sun
        candidate += timedelta(days=1)
    return candidate.replace(hour=9, minute=30, second=0, microsecond=0).astimezone(UTC)


def _is_market_hours(now: datetime) -> bool:
    """Check if current time is within US market hours (9:30-16:00 ET, weekdays)."""
    from zoneinfo import ZoneInfo
    et = now.astimezone(ZoneInfo("America/New_York"))
    if et.weekday() >= 5:  # Sat/Sun
        return False
    market_open = et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = et.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= et <= market_close


async def _scanner_loop(
    feed_service: CandidateFeedService,
    dashboard_runtime: DashboardRuntimeComposition,
    config: AppConfig,
    *,
    sentiment_analyzer: SentimentAnalyzer | None = None,
    adaptive_scorer: AdaptiveScorer | None = None,
) -> None:
    """Background scanner loop — runs inside the uvicorn process."""
    global _countdown_msg_id
    from app.providers.benzinga_adapter import BenzingaNewsProvider
    from app.providers.polygon_adapter import PolygonSnapshotProvider

    finnhub_key = os.environ.get("FINNHUB_API_KEY", "")

    # Telegram state: dedup + tick counter
    _last_alerted: dict[str, int] = {}  # symbol → last alerted score
    _tick_count = 0

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

            # Wait for market hours — send live countdown to Telegram
            if not _is_market_hours(now):
                next_open = _next_market_open(now)
                wait_seconds = (next_open - now).total_seconds()
                from zoneinfo import ZoneInfo
                next_et = next_open.astimezone(ZoneInfo("America/New_York"))

                hours = int(wait_seconds // 3600)
                mins = int((wait_seconds % 3600) // 60)
                countdown_str = f"{hours}h {mins}m" if hours else f"{mins}m"

                logger.info(
                    "Market closed — next open %s (%s away).",
                    next_et.strftime("%A %I:%M %p ET"), countdown_str,
                )

                # Send or edit live countdown on Telegram
                if _telegram_transport is not None:
                    from app.alerts.telegram_transport import TelegramTransportRequest, TelegramEditRequest
                    countdown_text = (
                        "⏳ <b>Market Closed</b>\n\n"
                        f"Next open: <b>{next_et.strftime('%A %b %d, %I:%M %p ET')}</b>\n"
                        f"Countdown: <b>{countdown_str}</b>\n\n"
                        "Scanner will auto-start when market opens.\n\n"
                        f"<i>Updated {now.strftime('%H:%M UTC')}</i>"
                    )
                    try:
                        if _countdown_msg_id is None:
                            receipt = _telegram_transport.send(TelegramTransportRequest(
                                chat_id=_startup_config.telegram.operator_chat_id,
                                text=countdown_text,
                            ))
                            _countdown_msg_id = receipt.delivery_id
                            logger.info("Telegram: countdown message sent (msg_id=%s)", _countdown_msg_id)
                        else:
                            _telegram_transport.edit(TelegramEditRequest(
                                chat_id=_startup_config.telegram.operator_chat_id,
                                message_id=_countdown_msg_id,
                                text=countdown_text,
                            ))
                            logger.info("Telegram: countdown updated (%s)", countdown_str)
                    except Exception as tg_err:
                        logger.warning("Telegram countdown failed: %s", tg_err)

                await asyncio.sleep(60)  # update every minute
                continue

            # Market just opened — update countdown message to "OPEN"
            if _countdown_msg_id is not None and _telegram_transport is not None:
                try:
                    from app.alerts.telegram_transport import TelegramEditRequest
                    _telegram_transport.edit(TelegramEditRequest(
                        chat_id=_startup_config.telegram.operator_chat_id,
                        message_id=_countdown_msg_id,
                        text="🟢 <b>Market is OPEN</b> — scanning now!",
                    ))
                except Exception:
                    pass
                _countdown_msg_id = None

            logger.info("── Scanner tick at %s ──", now.strftime("%H:%M:%S UTC"))
            try:
                # 1. Benzinga news — no ticker filter, discover all movers
                news_batch  = await benzinga.fetch_recent_news(limit=100)
                news_map    = latest_news_by_symbol(news_batch.records)
                active_syms = list(news_map.keys())[:40]

                logger.info("Benzinga: %d articles → %d unique symbols", len(news_batch.records), len(active_syms))
                if not active_syms:
                    logger.info("No active symbols, sleeping %ds", _SCAN_INTERVAL)
                    await asyncio.sleep(_SCAN_INTERVAL)
                    continue

                # 2. Finnhub quotes (batched to avoid rate limits — free tier: 60 calls/min)
                logger.info("Fetching Finnhub quotes for %d symbols …", len(active_syms))
                quote_results = []
                batch_size = 10
                for i in range(0, len(active_syms), batch_size):
                    batch = active_syms[i : i + batch_size]
                    batch_results = await asyncio.gather(
                        *[finnhub_quote(session, sym) for sym in batch]
                    )
                    quote_results.extend(batch_results)
                    if i + batch_size < len(active_syms):
                        await asyncio.sleep(1.0)  # pace between batches
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

                logger.info("Finnhub: %d/%d symbols got quotes", len(snapshots), len(active_syms))

                # 3. Polygon daily bars (RVOL history) — limit to 4 symbols to stay within free-tier rate limits
                daily_bars = ()
                poly_syms = [s for s in active_syms if s in snapshots][:4]
                try:
                    if poly_syms:
                        db = await polygon.fetch_daily_bars(poly_syms, lookback_days=20)
                        daily_bars = db.records
                        logger.info("Polygon: %d daily bar records for %d symbols", len(daily_bars), len(poly_syms))
                except Exception as poly_err:
                    logger.warning("Polygon daily bars failed: %s", poly_err)

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
                logger.info("yfinance: intraday bars for %d symbols", len(intraday_by_sym))

                # 4b. Fill missing snapshots from yfinance last bar (Finnhub rate-limit fallback)
                from app.providers.models import MarketSnapshot as _MS
                yf_filled = 0
                today = now.date()
                for sym, bars in intraday_by_sym.items():
                    if sym in snapshots or not bars:
                        continue
                    try:
                        today_bars = [b for b in bars if b.start_at.date() == today]
                        prev_bars = [b for b in bars if b.start_at.date() < today]
                        prev_close = str(prev_bars[-1].close_price) if prev_bars else None
                        use_bars = today_bars if today_bars else bars
                        last = use_bars[-1]
                        snapshots[sym] = _MS(
                            symbol=sym, provider="yfinance",
                            observed_at=last.start_at,
                            received_at=now,
                            last_price=last.close_price,
                            session_volume=sum(b.volume for b in use_bars),
                            previous_close=prev_close,
                            open_price=use_bars[0].open_price,
                            high_price=str(max(float(b.high_price) for b in use_bars)),
                            low_price=str(min(float(b.low_price) for b in use_bars if float(b.low_price) > 0)),
                        )
                        yf_filled += 1
                    except Exception:
                        continue
                if yf_filled:
                    logger.info("yfinance fallback: filled %d missing snapshots (total %d)", yf_filled, len(snapshots))

                # 5. LLM sentiment analysis (if configured)
                sentiment_verdicts = {}
                if sentiment_analyzer is not None:
                    try:
                        items = []
                        for sym in active_syms:
                            ln = news_map.get(sym)
                            if ln:
                                items.append((sym, ln.headline, None))
                        if items:
                            sentiment_verdicts = await sentiment_analyzer.analyze_batch(items)
                            logger.info("LLM analyzed %d/%d headlines", len(sentiment_verdicts), len(items))
                    except Exception as sent_err:
                        logger.warning("Sentiment batch failed: %s", sent_err)

                # 6. Build CandidateRows via full signal chain + intelligence
                candidate_rows = []
                projections = []
                for sym in active_syms:
                    linked_news = news_map.get(sym)
                    snapshot    = snapshots.get(sym)
                    if not linked_news or not snapshot:
                        continue

                    # ── Data enrichment: VWAP + bars ──
                    intraday = intraday_by_sym.get(sym, ())
                    today_bars = tuple(b for b in intraday if b.start_at.date() == today)

                    # Compute VWAP from intraday bars and enrich snapshot
                    enriched_snapshot = snapshot
                    if snapshot.vwap is None and today_bars:
                        total_pv = sum(
                            float(b.close_price) * b.volume
                            for b in today_bars if b.volume > 0
                        )
                        total_vol = sum(b.volume for b in today_bars)
                        if total_vol > 0:
                            computed_vwap = str(round(total_pv / total_vol, 4))
                            enriched_snapshot = MarketSnapshot(
                                symbol=snapshot.symbol,
                                provider=snapshot.provider,
                                observed_at=snapshot.observed_at,
                                received_at=snapshot.received_at,
                                last_price=snapshot.last_price,
                                session_volume=snapshot.session_volume or total_vol,
                                previous_close=snapshot.previous_close,
                                open_price=snapshot.open_price,
                                high_price=snapshot.high_price,
                                low_price=snapshot.low_price,
                                vwap=computed_vwap,
                            )

                    # Pick latest bar for short-term RVOL
                    current_bar = today_bars[-1] if today_bars else None

                    metrics = build_market_metrics(
                        enriched_snapshot,
                        daily_bars=daily_bars,
                        current_bar=current_bar,
                        historical_intraday_bars=intraday,
                        lookback_days=20,
                    )
                    row = build_candidate_row(enriched_snapshot, linked_news, metrics)
                    if row is None:
                        continue

                    # Derive pullback volume: lighter if recent bars have lower avg volume
                    pullback_lighter = None
                    if len(today_bars) >= 10:
                        first_half_vol = sum(b.volume for b in today_bars[:len(today_bars)//2])
                        second_half_vol = sum(b.volume for b in today_bars[len(today_bars)//2:])
                        pullback_lighter = second_half_vol < first_half_vol

                    context = build_context_features(
                        enriched_snapshot,
                        intraday_bars=intraday,
                        pullback_volume_lighter=pullback_lighter,
                    )
                    validity    = evaluate_setup_validity(row, linked_news, context)

                    # Trigger: preferred=15s (no 15s bars yet), fallback=60s (yfinance 1m)
                    trigger_sel  = resolve_trigger_bars(preferred_bars=(), fallback_bars=intraday)
                    trigger      = evaluate_first_break_trigger(trigger_sel)

                    # Invalidation gate
                    invalidation = evaluate_invalidation(
                        row, linked_news, context, setup_validity=validity
                    )

                    # Intelligence layer: sentiment + adaptive learning
                    sentiment_mult = None
                    adaptive_adj = None

                    verdict = sentiment_verdicts.get(sym)
                    if verdict is not None:
                        sentiment_mult = verdict.score_multiplier

                    if adaptive_scorer is not None:
                        adjustment = adaptive_scorer.compute_adjustment(
                            catalyst_tag=row.catalyst_tag.value,
                            daily_rvol=row.daily_relative_volume,
                            hour_of_day=now.hour,
                            sentiment_direction=verdict.direction.value if verdict else None,
                        )
                        adaptive_adj = adjustment.total_adjustment

                    proj = project_strategy_row(
                        row,
                        context_features=context,
                        setup_validity=validity,
                        trigger_evaluation=trigger,
                        invalidation=invalidation,
                        sentiment_multiplier=sentiment_mult,
                        adaptive_adjustment=adaptive_adj,
                    )
                    candidate_rows.append(row)
                    projections.append(proj)

                logger.info("Signal chain: %d candidates built from %d active symbols", len(candidate_rows), len(active_syms))
                for p in projections:
                    logger.info("  → %s  price=%s  score=%d  stage=%s  %s",
                                p.row.symbol, p.row.price, p.score, p.stage_tag.value,
                                p.primary_invalid_reason or "valid")

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
                elapsed = (datetime.now(UTC) - scan_start).total_seconds()
                logger.info("── Scan complete: %d candidates, %.1fs elapsed ──", len(candidate_rows), elapsed)

                # 7. Telegram — smart 3-tier messaging
                if _telegram_transport is not None:
                    from app.alerts.telegram_transport import TelegramTransportRequest

                    valid   = [p for p in projections if p.is_valid]
                    building = [p for p in valid if p.stage_tag.value == "building"]
                    triggered = [p for p in valid if p.stage_tag.value == "trigger_ready"]
                    invalid = [p for p in projections if not p.is_valid]

                    # ── Tier 1: Instant actionable alerts for new/changed valid setups ──
                    for p in sorted(valid, key=lambda x: x.score, reverse=True)[:5]:
                        sym = p.row.symbol
                        prev_score = _last_alerted.get(sym)
                        if prev_score is not None and abs(p.score - prev_score) < 5:
                            continue  # already alerted, score hasn't changed much

                        _last_alerted[sym] = p.score
                        sentiment = sentiment_verdicts.get(sym)
                        sent_dot = ""
                        if sentiment:
                            sent_dot = {"bullish": " 🟢", "bearish": " 🔴"}.get(
                                sentiment.direction.value, ""
                            )

                        stage_icon = "⚡" if p.stage_tag.value == "trigger_ready" else "🔨"
                        stage_label = (
                            "trigger fired" if p.stage_tag.value == "trigger_ready"
                            else "building"
                        )

                        # Compute entry / stop / target
                        entry_price = p.row.price
                        stop_price = None
                        target_1 = None
                        target_2 = None
                        rr_ratio = ""
                        risk_per_share = ""
                        if entry_price is not None:
                            # Stop: use pullback low from context, or 2% below entry
                            if (p.invalidation is None or not p.invalidation.invalidated):
                                sym_snapshot = snapshots.get(sym)
                                if sym_snapshot is not None:
                                    ctx = build_context_features(
                                        sym_snapshot,
                                        intraday_bars=intraday_by_sym.get(sym, ()),
                                    )
                                    if ctx.pullback_low is not None and ctx.pullback_low < entry_price:
                                        stop_price = ctx.pullback_low
                            if stop_price is None:
                                stop_price = round(float(entry_price) * Decimal("0.98"), 2)
                                stop_price = Decimal(str(stop_price))

                            risk = float(entry_price) - float(stop_price)
                            if risk > 0:
                                target_1 = Decimal(str(round(float(entry_price) + risk * 1.5, 2)))
                                target_2 = Decimal(str(round(float(entry_price) + risk * 2.5, 2)))
                                rr_ratio = f"R:R  1:{round(1.5, 1)}"
                                risk_per_share = f"Risk ${risk:.2f}/share"

                        catalyst_label = p.row.catalyst_tag.value.replace("_", " ").title()
                        chg = ""
                        if p.row.change_from_prior_close_percent is not None:
                            chg = f"↑{p.row.change_from_prior_close_percent:.1f}%"

                        lines = [
                            f"🔔 <b>NEW SETUP — {sym}</b>",
                            "",
                            f"🟢 BUY  │  score {p.score}/100  │  {stage_icon} {stage_label}{sent_dot}",
                            "",
                        ]
                        if entry_price is not None:
                            lines.append(f"Entry:    <code>${entry_price}</code>")
                        if stop_price is not None:
                            lines.append(f"Stop:     <code>${stop_price}</code>  🛑")
                        if target_1 is not None:
                            lines.append(f"Target₁:  <code>${target_1}</code>  🎯")
                        if target_2 is not None:
                            lines.append(f"Target₂:  <code>${target_2}</code>  🎯")
                        if rr_ratio or risk_per_share:
                            lines.append("")
                            parts = [x for x in [rr_ratio, risk_per_share] if x]
                            lines.append("  │  ".join(parts))

                        # Stats line
                        lines.append("")
                        lines.append("📊 <b>Stats</b>")
                        stats = []
                        if p.row.daily_relative_volume is not None:
                            stats.append(f"RVOL {p.row.daily_relative_volume:.1f}x")
                        if chg:
                            stats.append(chg)
                        stats.append(f"Catalyst: {catalyst_label}")
                        lines.append("  │  ".join(stats))

                        # Headline
                        lines.append("")
                        lines.append(f"💡 {p.row.headline[:55]}")

                        text = "\n".join(lines)
                        try:
                            _telegram_transport.send(TelegramTransportRequest(
                                chat_id=_startup_config.telegram.operator_chat_id,
                                text=text,
                            ))
                            logger.info("Telegram actionable alert sent: %s (score %d)", sym, p.score)
                        except Exception as tg_err:
                            logger.warning("Telegram alert send failed: %s", tg_err)

                    # ── Tier 2: Periodic scan summary (every 5th tick) ──
                    if not valid and _tick_count % 5 == 0 and projections:
                        summary_lines = [
                            f"📊 <b>SCAN</b> — {now.strftime('%H:%M:%S UTC')}  │  {elapsed:.1f}s",
                            "",
                            f"⚡ {len(triggered)} actionable  │  🔨 {len(building)} building  │  ❌ {len(invalid)} invalid",
                        ]
                        # Show top building setups (almost ready)
                        top_building = sorted(building, key=lambda x: x.score, reverse=True)[:3]
                        if top_building:
                            summary_lines.append("")
                            summary_lines.append("<b>Top Building:</b>")
                            for bp in top_building:
                                bchg = f"↑{bp.row.change_from_prior_close_percent:.1f}%" if bp.row.change_from_prior_close_percent else ""
                                brvol = f"RVOL {bp.row.daily_relative_volume:.1f}x" if bp.row.daily_relative_volume else ""
                                summary_lines.append(
                                    f"• {bp.row.symbol}  ${bp.row.price}  {bchg}  {brvol}  score {bp.score}"
                                )
                        try:
                            _telegram_transport.send(TelegramTransportRequest(
                                chat_id=_startup_config.telegram.operator_chat_id,
                                text="\n".join(summary_lines),
                            ))
                            logger.info("Telegram scan summary sent")
                        except Exception as tg_err:
                            logger.warning("Telegram summary send failed: %s", tg_err)

                    # ── Tier 3: Heartbeat (every 10th tick, no valid setups) ──
                    elif not valid and _tick_count % 10 == 0:
                        heartbeat = (
                            f"💤 Scanner alive — {now.strftime('%H:%M:%S UTC')}"
                            f"  │  {len(projections)} scanned  │  0 actionable"
                        )
                        try:
                            _telegram_transport.send(TelegramTransportRequest(
                                chat_id=_startup_config.telegram.operator_chat_id,
                                text=heartbeat,
                            ))
                        except Exception:
                            pass

                    _tick_count += 1

            except Exception as exc:
                logger.error("Scanner loop error: %s", exc, exc_info=True)
                scanner_snap = ScannerLoopSnapshot(
                    observed_at=now,
                    last_success_at=None,
                    last_error=str(exc)[:200],
                )
                dashboard_runtime.set_scanner_loop(scanner_snap)

            await asyncio.sleep(_SCAN_INTERVAL)


# ── Shared state: scanner loop + HTTP dashboard read from the same runtime ────

_startup_config = AppConfig.from_env()
_shared_dashboard_runtime = create_default_dashboard_runtime()

_telegram_transport: HttpTelegramTransport | None = None

if _startup_config.telegram.is_configured:
    _telegram_transport = HttpTelegramTransport(_startup_config.telegram.bot_token)  # type: ignore[arg-type]
    _telegram_runtime = create_telegram_operator_runtime(
        transport=_telegram_transport,
        operator_chat_id=_startup_config.telegram.operator_chat_id,  # type: ignore[arg-type]
        dashboard_runtime=_shared_dashboard_runtime,
    )
    _shared_feed_service = _telegram_runtime.feed_service
    _http_app = _telegram_runtime.app
    logger.info("Telegram: operator runtime enabled (chat_id=%s)", _startup_config.telegram.operator_chat_id)
else:
    _shared_feed_service = CandidateFeedService()
    _http_app = create_app(dashboard_runtime=_shared_dashboard_runtime)
    logger.info("Telegram: disabled (no TELEGRAM_BOT_TOKEN)")

# ── Intelligence layer initialization ─────────────────────────────────────────

_sentiment_analyzer: SentimentAnalyzer | None = None
if _startup_config.openai.is_configured:
    _sentiment_analyzer = SentimentAnalyzer(
        api_key=_startup_config.openai.api_key,  # type: ignore[arg-type]
        model=_startup_config.openai.model,
        temperature=_startup_config.openai.temperature,
    )
    logger.info("Intelligence: LLM sentiment analyzer enabled (model=%s)", _startup_config.openai.model)
else:
    logger.info("Intelligence: LLM sentiment analyzer disabled (no OPENAI_API_KEY)")

_outcome_store = OutcomeStore()
_adaptive_scorer = AdaptiveScorer(_outcome_store)
logger.info("Intelligence: adaptive learning layer enabled (store=%s)", _outcome_store.path)

_countdown_msg_id: str | None = None
_scanner_task: asyncio.Task | None = None


async def _lifespan(scope, receive, send) -> None:
    """ASGI lifespan handler — starts scanner background task on startup."""
    global _scanner_task, _countdown_msg_id
    event = await receive()
    if event["type"] == "lifespan.startup":
        # Send startup confirmation to Telegram with market status + countdown
        if _telegram_transport is not None:
            try:
                from app.alerts.telegram_transport import TelegramTransportRequest
                from zoneinfo import ZoneInfo
                now = datetime.now(UTC)
                if _is_market_hours(now):
                    status_text = "✅ <b>Scanner Online</b>\n\n🟢 Market is OPEN — scanning now."
                else:
                    next_open = _next_market_open(now)
                    next_et = next_open.astimezone(ZoneInfo("America/New_York"))
                    wait_secs = (next_open - now).total_seconds()
                    hours = int(wait_secs // 3600)
                    mins = int((wait_secs % 3600) // 60)
                    countdown_str = f"{hours}h {mins}m" if hours else f"{mins}m"
                    status_text = (
                        "⏳ <b>Scanner Online — Market Closed</b>\n\n"
                        f"Next open: <b>{next_et.strftime('%A %b %d, %I:%M %p ET')}</b>\n"
                        f"Countdown: <b>{countdown_str}</b>\n\n"
                        "Scanner will auto-start when market opens.\n\n"
                        f"<i>Updated {now.strftime('%H:%M UTC')}</i>"
                    )
                receipt = _telegram_transport.send(TelegramTransportRequest(
                    chat_id=_startup_config.telegram.operator_chat_id,
                    text=status_text,
                ))
                # Store message_id so scanner loop can edit the countdown
                if not _is_market_hours(now):
                    _countdown_msg_id = receipt.delivery_id
                logger.info("Telegram: startup confirmation sent (msg_id=%s)", receipt.delivery_id)
            except Exception as tg_err:
                logger.warning("Telegram startup message failed: %s", tg_err)

        _scanner_task = asyncio.create_task(
            _scanner_loop(
                _shared_feed_service,
                _shared_dashboard_runtime,
                _startup_config,
                sentiment_analyzer=_sentiment_analyzer,
                adaptive_scorer=_adaptive_scorer,
            )
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
