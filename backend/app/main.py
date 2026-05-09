from __future__ import annotations

import asyncio
import html
import json
import logging
import os
from collections import Counter
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import aiohttp
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

from app.agents import (
    TradingAgentsReviewConfig,
    TradingAgentsReviewResult,
    TradingAgentsReviewer,
    TradingAgentsReviewStore,
)
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
from app.providers.errors import ProviderError
from app.runtime.session_window import RuntimeWindow
from app.scanner.feed_service import CandidateFeedService
from app.scanner.row_builder import build_candidate_row
from app.scanner.metrics import build_market_metrics
from app.scanner.news_linking import latest_news_by_symbol
from app.scanner.context_features import build_context_features
from app.scanner.invalidation import evaluate_invalidation
from app.scanner.setup_validity import evaluate_setup_validity
from app.scanner.session_bars import bars_before_session, bars_for_session
from app.scanner.strategy_defaults import StrategyDefaults
from app.scanner.strategy_projection import project_strategy_row
from app.scanner.trigger_logic import evaluate_first_break_trigger
from app.scanner.trigger_policy import resolve_trigger_bars
from app.dashboard.scanner_state import ScannerRow, get_scanner_state
from app.dashboard.alerted_setups_state import AlertedSetup, get_alerted_setups_state
from app.dashboard.scanner_dashboard import render_scanner_dashboard
from app.intelligence.models import OutcomeRecord, TradeOutcome

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

_STRATEGY_DEFAULTS = StrategyDefaults()


def _agent_review_plain_text(result: TradingAgentsReviewResult, *, limit: int = 900) -> str:
    if result.status == "ok":
        raw = result.decision
    else:
        raw = result.error or result.status

    if isinstance(raw, (dict, list, tuple)):
        text = json.dumps(raw, default=str, ensure_ascii=False)
    else:
        text = str(raw)

    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text


def _agent_review_text(result: TradingAgentsReviewResult, *, limit: int = 900) -> str:
    text = _agent_review_plain_text(result, limit=limit)
    return html.escape(text)


async def _run_agent_review(
    reviewer: TradingAgentsReviewer,
    store: TradingAgentsReviewStore | None,
    *,
    symbol: str,
    trade_date: str,
    timeout_seconds: float,
    context: dict[str, object],
) -> TradingAgentsReviewResult:
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(reviewer.review, symbol, trade_date),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        result = TradingAgentsReviewResult(
            ticker=symbol,
            trade_date=trade_date,
            status="error",
            decision=None,
            llm_provider=reviewer.config.llm_provider,
            deep_model=reviewer.config.deep_model,
            quick_model=reviewer.config.quick_model,
            error=f"TradingAgents review timed out after {timeout_seconds:.0f}s",
        )

    if store is not None:
        try:
            store.append(result, context=context)
        except Exception as exc:
            logger.warning("TradingAgents: failed to save review for %s: %s", symbol, exc)

    return result


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
        # ── Scanner dashboard + API routes ──
        if path == "/scanner" or path == "/scanner/":
            html = render_scanner_dashboard()
            await _send_bytes(send, status_code=200, body=html.encode("utf-8"), content_type=b"text/html; charset=utf-8")
            return
        if path == "/api/scanner":
            data = get_scanner_state().to_json_bytes()
            await _send_bytes(send, status_code=200, body=data, content_type=b"application/json")
            return
        if path == "/api/alerted-setups":
            # Active + recently-closed setups for the dashboard hero panel.
            data = get_alerted_setups_state().to_json_bytes()
            await _send_bytes(send, status_code=200, body=data, content_type=b"application/json")
            return
        if path == "/api/learning-summary":
            # What has the adaptive learning layer actually learned so far?
            # (Returns {status: "no_data"} until trades start closing.)
            try:
                summary = _adaptive_scorer.get_learning_summary() if _adaptive_scorer else {"status": "disabled"}
            except Exception as exc:
                summary = {"status": "error", "error": str(exc)}
            body = json.dumps(summary).encode("utf-8")
            await _send_bytes(send, status_code=200, body=body, content_type=b"application/json")
            return
        if path == "/health":
            await _send_bytes(send, status_code=200, body=b'{"status":"ok"}', content_type=b"application/json")
            return

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

_SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL_SEC", "60"))
_MIN_GAP_PERCENT = float(os.environ.get("MIN_GAP_PERCENT", "5.0"))


def _quote_float(raw_quote: dict, *field_names: str) -> float | None:
    for field_name in field_names:
        value = raw_quote.get(field_name)
        if isinstance(value, dict):
            value = value.get("raw") or value.get("fmt")
        if value is None:
            continue
        try:
            return float(str(value).replace("%", "").replace(",", ""))
        except (TypeError, ValueError):
            continue
    return None


def _quote_int(raw_quote: dict, *field_names: str) -> int:
    value = _quote_float(raw_quote, *field_names)
    return int(value) if value is not None else 0


def _mover_from_quote(raw_quote: dict, *, min_gap_percent: float) -> dict | None:
    sym = str(raw_quote.get("symbol") or "").strip().upper()
    pct = _quote_float(raw_quote, "regularMarketChangePercent", "percentchange", "percentChange")
    price = _quote_float(raw_quote, "regularMarketPrice", "intradayprice", "regularMarketPreviousClose")
    volume = _quote_int(raw_quote, "regularMarketVolume", "dayvolume", "volume")
    avg_vol = _quote_int(raw_quote, "averageDailyVolume3Month", "averageDailyVolume10Day", "avgdailyvol3m")
    prev_close = _quote_float(raw_quote, "regularMarketPreviousClose", "previousClose")

    if not sym or pct is None or pct < min_gap_percent or price is None:
        return None

    return {
        "symbol": sym,
        "change_percent": round(pct, 2),
        "price": price,
        "volume": volume,
        "avg_volume": avg_vol or 1,
        "rvol": round(volume / avg_vol, 2) if avg_vol else 0,
        "prev_close": prev_close or 0,
        "day_high": _quote_float(raw_quote, "regularMarketDayHigh", "dayHigh") or price,
        "day_low": _quote_float(raw_quote, "regularMarketDayLow", "dayLow") or price,
    }


def _parse_movers_from_quotes(raw_quotes: list[dict], *, min_gap_percent: float) -> list[dict]:
    by_symbol: dict[str, dict] = {}
    for raw_quote in raw_quotes:
        mover = _mover_from_quote(raw_quote, min_gap_percent=min_gap_percent)
        if mover is not None:
            by_symbol[mover["symbol"]] = mover
    movers = list(by_symbol.values())
    movers.sort(key=lambda m: m["change_percent"], reverse=True)
    return movers


def _discover_movers() -> list[dict]:
    """Fetch today's top gainers from Yahoo Finance screener.

    Returns list of dicts with keys: symbol, change_percent, price, volume,
    avg_volume, rvol, prev_close, day_high, day_low.
    Runs synchronously (yfinance uses requests internally).
    """
    screen_errors: list[str] = []

    try:
        screen = yf.screen("day_gainers", count=50)
        quotes = screen.get("quotes", []) if isinstance(screen, dict) else []
        movers = _parse_movers_from_quotes(quotes, min_gap_percent=_MIN_GAP_PERCENT)
        if movers:
            return movers
    except Exception as exc:
        screen_errors.append(f"day_gainers: {exc}")

    try:
        from yfinance import EquityQuery

        query = EquityQuery("and", [
            EquityQuery("gt", ["percentchange", _MIN_GAP_PERCENT]),
            EquityQuery("eq", ["region", "us"]),
            EquityQuery("gte", ["intradayprice", 1]),
            EquityQuery("gt", ["dayvolume", 50_000]),
            EquityQuery("is-in", ["exchange", "NMS", "NYQ"]),
        ])
        screen = yf.screen(query, sortField="percentchange", sortAsc=False, size=50)
        quotes = screen.get("quotes", []) if isinstance(screen, dict) else []
        movers = _parse_movers_from_quotes(quotes, min_gap_percent=_MIN_GAP_PERCENT)
        if movers:
            return movers
    except Exception as exc:
        screen_errors.append(f"equity_query: {exc}")

    logger.warning(
        "Yahoo movers returned zero stocks above %.1f%% (%s)",
        _MIN_GAP_PERCENT,
        "; ".join(screen_errors) if screen_errors else "no screener matches",
    )
    return []


def _fetch_float_data(symbols: list[str]) -> dict[str, float]:
    """Fetch float (shares available to trade) for a batch of symbols via yfinance.

    Returns {symbol: float_shares} dict. Runs synchronously.
    """
    if not symbols:
        return {}
    result = {}
    try:
        tickers = yf.Tickers(" ".join(symbols[:50]))
        for sym in symbols[:50]:
            try:
                info = tickers.tickers[sym].info
                # Try floatShares first, fall back to sharesOutstanding
                float_val = info.get("floatShares") or info.get("sharesOutstanding")
                if float_val and float_val > 0:
                    result[sym] = float(float_val)
            except Exception:
                continue
    except Exception:
        pass
    return result


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


def _record_setup_outcome(
    setup: AlertedSetup,
    *,
    outcome_store: "OutcomeStore",
) -> None:
    """Map a terminal lifecycle state → OutcomeRecord and persist it.
    Feeds the adaptive learning layer so win-rate by catalyst / hour / RVOL
    starts accumulating. Non-terminal stages (alerted, t1_hit) are skipped."""
    if not setup.is_terminal_stage:
        return

    outcome: TradeOutcome
    exit_price: Decimal | None = None
    realized_pnl: Decimal | None = None

    if setup.stage == "t2_hit":
        outcome = TradeOutcome.WIN
        exit_price = setup.target_2
        realized_pnl = setup.target_2 - setup.entry_price
    elif setup.stage == "stopped":
        # If peak reached T1, user would have moved stop → breakeven.
        # Otherwise a clean −1R loss.
        hit_t1 = setup.peak_price is not None and setup.peak_price >= setup.target_1
        if hit_t1:
            outcome = TradeOutcome.BREAKEVEN
            exit_price = setup.entry_price
            realized_pnl = Decimal("0")
        else:
            outcome = TradeOutcome.LOSS
            exit_price = setup.stop_price
            realized_pnl = setup.stop_price - setup.entry_price
    elif setup.stage == "invalidated":
        outcome = TradeOutcome.LOSS
        exit_price = setup.stop_price
        realized_pnl = setup.stop_price - setup.entry_price
    elif setup.stage == "expired":
        outcome = TradeOutcome.BREAKEVEN
        exit_price = setup.entry_price
        realized_pnl = Decimal("0")
    else:
        return

    try:
        record = OutcomeRecord(
            trade_id=f"setup:{setup.symbol}:{int(setup.first_alerted_at.timestamp())}",
            symbol=setup.symbol,
            entered_at=setup.first_alerted_at,
            closed_at=setup.closed_at,
            catalyst_tag=setup.catalyst_tag or "unknown",
            catalyst_quality=setup.catalyst_quality,
            sentiment_direction=setup.sentiment_direction,
            sentiment_confidence=setup.sentiment_confidence,
            entry_price=setup.entry_price,
            stop_price=setup.stop_price,
            target_price=setup.target_1,
            score_at_entry=setup.score_at_entry,
            daily_rvol=setup.daily_rvol,
            short_term_rvol=setup.short_term_rvol,
            change_percent=setup.change_percent,
            gap_percent=setup.gap_percent,
            hour_of_day=setup.first_alerted_at.hour,
            exit_price=exit_price,
            realized_pnl=realized_pnl,
            outcome=outcome,
        )
        outcome_store.record_outcome(record)
        logger.info(
            "Learning: recorded %s for %s (stage=%s pnl=%s)",
            outcome.value, setup.symbol, setup.stage, realized_pnl,
        )
    except Exception as exc:
        logger.warning(
            "Learning: failed to record outcome for %s: %s", setup.symbol, exc,
        )


async def _scanner_loop(
    feed_service: CandidateFeedService,
    dashboard_runtime: DashboardRuntimeComposition,
    config: AppConfig,
    *,
    sentiment_analyzer: SentimentAnalyzer | None = None,
    adaptive_scorer: AdaptiveScorer | None = None,
    agent_reviewer: TradingAgentsReviewer | None = None,
    agent_review_store: TradingAgentsReviewStore | None = None,
) -> None:
    """Background scanner loop — runs inside the uvicorn process."""
    global _countdown_msg_id
    from app.providers.benzinga_adapter import BenzingaNewsProvider
    from app.providers.polygon_adapter import PolygonSnapshotProvider

    finnhub_key = os.environ.get("FINNHUB_API_KEY", "")

    # Telegram state: one active setup per symbol + tick counter.
    # Key invariant: at most one "NEW SETUP" message per symbol until the
    # setup reaches a terminal state (t2_hit / stopped / invalidated / expired)
    # and a re-alert cooldown passes.
    _alerted_setups: dict[str, AlertedSetup] = {}
    _REALERT_COOLDOWN_SEC = 60 * 60       # wait 60 min after close before re-alerting same sym
    _TRIGGER_EXPIRY_SEC = 15 * 60         # trigger → T1-hit window; past this = expired
    _tick_count = 0
    _last_building_digest: tuple[tuple[str, int], ...] = ()

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
                            receipt = await _telegram_transport.async_send(TelegramTransportRequest(
                                chat_id=_startup_config.telegram.operator_chat_id,
                                text=countdown_text,
                            ))
                            _countdown_msg_id = receipt.delivery_id
                            logger.info("Telegram: countdown message sent (msg_id=%s)", _countdown_msg_id)
                        else:
                            await _telegram_transport.async_edit(TelegramEditRequest(
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
                    await _telegram_transport.async_edit(TelegramEditRequest(
                        chat_id=_startup_config.telegram.operator_chat_id,
                        message_id=_countdown_msg_id,
                        text="🟢 <b>Market is OPEN</b> — scanning now!",
                    ))
                except Exception:
                    pass
                _countdown_msg_id = None

            logger.info("── Scanner tick at %s ──", now.strftime("%H:%M:%S UTC"))
            loop = asyncio.get_running_loop()
            try:
                # 1a. Discover real movers from Yahoo Finance (gappers ≥ MIN_GAP_PERCENT)
                movers = await loop.run_in_executor(None, _discover_movers)
                mover_syms = [m["symbol"] for m in movers]
                mover_snapshots_prefill: dict[str, dict] = {m["symbol"]: m for m in movers}
                logger.info(
                    "Yahoo movers: %d stocks gapping ≥%.0f%% — %s",
                    len(movers), _MIN_GAP_PERCENT,
                    ", ".join(f'{m["symbol"]} +{m["change_percent"]}%' for m in movers[:8]),
                )

                # 1b. Benzinga news — enrich movers with catalyst + pick up any extras.
                # If Benzinga is temporarily unavailable, continue with mover-only
                # synthetic catalysts instead of failing the whole scan.
                try:
                    news_batch = await benzinga.fetch_recent_news(limit=100)
                    news_map = latest_news_by_symbol(news_batch.records)
                    bz_syms = set(news_map.keys())
                except ProviderError as bz_err:
                    if not bz_err.retriable:
                        raise
                    logger.warning("Benzinga news failed; continuing with mover-only scan: %s", bz_err)
                    news_map = {}
                    bz_syms = set()

                # Priority: movers first (real gappers), then Benzinga-only symbols
                active_syms = list(dict.fromkeys(mover_syms + [s for s in bz_syms if s not in mover_syms]))[:50]

                logger.info(
                    "Symbol universe: %d movers + %d Benzinga-only → %d total",
                    len(mover_syms), len([s for s in active_syms if s not in mover_syms]), len(active_syms),
                )
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

                # 2b. Pre-fill movers from Yahoo data (covers symbols Finnhub missed)
                for sym, mdata in mover_snapshots_prefill.items():
                    if sym not in snapshots and mdata["price"]:
                        try:
                            snapshots[sym] = MarketSnapshot(
                                symbol=sym, provider="yahoo_screener",
                                observed_at=now, received_at=now,
                                last_price=str(mdata["price"]),
                                session_volume=int(mdata["volume"]),
                                previous_close=str(mdata["prev_close"]) if mdata["prev_close"] else None,
                                high_price=str(mdata["day_high"]) if mdata["day_high"] else None,
                                low_price=str(mdata["day_low"]) if mdata["day_low"] else None,
                            )
                        except Exception:
                            continue
                if mover_snapshots_prefill:
                    logger.info("Yahoo pre-fill: %d mover snapshots added", len([s for s in mover_snapshots_prefill if s in snapshots]))

                # 2c. Float data (yfinance) — run in thread
                float_data: dict[str, float] = {}
                try:
                    float_data = await loop.run_in_executor(None, _fetch_float_data, active_syms)
                    logger.info("Float data: %d/%d symbols", len(float_data), len(active_syms))
                except Exception as float_err:
                    logger.warning("Float fetch failed: %s", float_err)

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
                #    Batched to avoid timeouts on large symbol lists
                _YF_BATCH_SIZE = 10

                def _yf_bars_batch(symbols: list[str]) -> dict:
                    """Download intraday bars for a batch of symbols. Returns {sym: tuple[IntradayBar]}."""
                    import math
                    from app.providers.models import IntradayBar
                    try:
                        raw = yf.download(" ".join(symbols), period="2d",
                                          interval="1m", progress=False, group_by="ticker",
                                          timeout=30)
                    except Exception as yf_err:
                        logger.warning("yfinance batch download failed for %d symbols: %s", len(symbols), yf_err)
                        return {}
                    result = {}
                    for sym in symbols:
                        try:
                            df = raw if len(symbols) == 1 else (
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
                        except Exception as parse_err:
                            logger.warning("yfinance parse failed for %s: %s", sym, parse_err)
                            continue
                    return result

                def _yf_bars_all():
                    """Download intraday bars in batches of _YF_BATCH_SIZE with retry."""
                    combined = {}
                    for i in range(0, len(active_syms), _YF_BATCH_SIZE):
                        batch = active_syms[i : i + _YF_BATCH_SIZE]
                        batch_result = _yf_bars_batch(batch)
                        if not batch_result:
                            # Retry once on failure
                            logger.info("yfinance: retrying batch %d-%d (%s …)", i, i + len(batch), batch[0])
                            import time; time.sleep(2)
                            batch_result = _yf_bars_batch(batch)
                        combined.update(batch_result)
                        logger.info("yfinance: batch %d-%d → %d/%d symbols got bars",
                                    i, i + len(batch), len(batch_result), len(batch))
                    return combined

                intraday_by_sym = await loop.run_in_executor(None, _yf_bars_all)
                logger.info("yfinance: intraday bars for %d/%d symbols", len(intraday_by_sym), len(active_syms))

                # 4b. Fill missing snapshots from yfinance last bar (Finnhub rate-limit fallback)
                from app.providers.models import MarketSnapshot as _MS
                yf_filled = 0
                for sym, bars in intraday_by_sym.items():
                    if sym in snapshots or not bars:
                        continue
                    try:
                        today_bars = bars_for_session(bars, as_of=now)
                        prev_bars = bars_before_session(bars, as_of=now)
                        if not today_bars:
                            continue
                        prev_close = str(prev_bars[-1].close_price) if prev_bars else None
                        use_bars = today_bars
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
                                body = getattr(ln.latest_event, "summary", None)
                                items.append((sym, ln.headline, body))
                        if items:
                            sentiment_verdicts = await sentiment_analyzer.analyze_batch(items)
                            logger.info("LLM analyzed %d/%d headlines", len(sentiment_verdicts), len(items))
                    except Exception as sent_err:
                        logger.warning("Sentiment batch failed: %s", sent_err)

                # 5b. Synthesize news entries for movers without Benzinga coverage
                from app.providers.models import NewsEvent, CatalystTag
                from app.scanner.models import LinkedNewsEvent
                for sym in mover_syms:
                    if sym not in news_map and sym in snapshots:
                        mdata = mover_snapshots_prefill[sym]
                        synthetic_event = NewsEvent(
                            event_id=f"yf-gapper-{sym}-{now.isoformat()}",
                            provider="yahoo_screener",
                            published_at=now,
                            received_at=now,
                            headline=f"{sym} gapping +{mdata['change_percent']}% on unusual volume",
                            symbols=(sym,),
                            catalyst_tag=CatalystTag.UNKNOWN,
                            summary=f"Detected via Yahoo Finance screener: +{mdata['change_percent']}% with RVOL {mdata['rvol']}x",
                        )
                        news_map[sym] = LinkedNewsEvent(
                            symbol=sym,
                            latest_event=synthetic_event,
                            latest_event_at=now,
                            related_events=(synthetic_event,),
                        )
                        logger.info("Synthetic news created for mover: %s +%.1f%%", sym, mdata["change_percent"])

                # 6. Build CandidateRows via full signal chain + intelligence
                candidate_rows = []
                projections = []
                enriched_snapshots: dict[str, MarketSnapshot] = {}  # sym → enriched (with VWAP)
                for sym in active_syms:
                    linked_news = news_map.get(sym)
                    snapshot    = snapshots.get(sym)
                    if not linked_news or not snapshot:
                        continue

                    # ── Data enrichment: VWAP + bars ──
                    intraday = intraday_by_sym.get(sym, ())
                    today_bars = bars_for_session(intraday, as_of=now)

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

                    enriched_snapshots[sym] = enriched_snapshot

                    # Pick latest bar for short-term RVOL
                    current_bar = today_bars[-1] if today_bars else None

                    metrics = build_market_metrics(
                        enriched_snapshot,
                        daily_bars=daily_bars,
                        current_bar=current_bar,
                        historical_intraday_bars=intraday,
                        lookback_days=20,
                    )
                    # Patch: inject time-adjusted Yahoo RVOL for movers missing Polygon daily bars
                    if metrics.daily_relative_volume is None and sym in mover_snapshots_prefill:
                        mdata = mover_snapshots_prefill[sym]
                        from app.scanner.metrics import MarketMetrics
                        from zoneinfo import ZoneInfo
                        _et_now = now.astimezone(ZoneInfo("America/New_York"))
                        # Minutes elapsed since 9:30 AM ET (max 390 min trading day)
                        _mins_since_open = max(1, (_et_now.hour * 60 + _et_now.minute) - 570)
                        _day_fraction = min(1.0, _mins_since_open / 390)
                        # Project current volume to full-day pace
                        projected_vol = mdata["volume"] / _day_fraction if _day_fraction > 0 else mdata["volume"]
                        avg_vol = mdata["avg_volume"] or 1
                        yahoo_rvol = Decimal(str(round(projected_vol / avg_vol, 2)))
                        yahoo_adv = Decimal(str(avg_vol))
                        metrics = MarketMetrics(
                            average_daily_volume=yahoo_adv,
                            daily_relative_volume=yahoo_rvol,
                            short_term_relative_volume=metrics.short_term_relative_volume or yahoo_rvol,
                            gap_percent=metrics.gap_percent,
                            change_from_prior_close_percent=metrics.change_from_prior_close_percent,
                            pullback_from_high_percent=metrics.pullback_from_high_percent,
                        )
                    sym_float = Decimal(str(float_data[sym])) if sym in float_data else None
                    row = build_candidate_row(enriched_snapshot, linked_news, metrics, float_shares=sym_float)
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
                        intraday_bars=today_bars,
                        pullback_volume_lighter=pullback_lighter,
                    )
                    validity    = evaluate_setup_validity(row, linked_news, context)
                    # Trigger: preferred=15s (no 15s bars yet), fallback=60s (yfinance 1m)
                    trigger_sel  = resolve_trigger_bars(preferred_bars=(), fallback_bars=today_bars)
                    trigger      = evaluate_first_break_trigger(
                        trigger_sel,
                        as_of=now,
                        max_trigger_age_seconds=_STRATEGY_DEFAULTS.max_trigger_age_seconds,
                    )

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

                # 5c. Push scanner data to shared state for dashboard API
                _scanner_rows = []
                for p in projections:
                    r = p.row
                    sv = p.setup_validity
                    verdict = sentiment_verdicts.get(r.symbol)
                    # Surface trigger metadata so the dashboard can show when it fired
                    te = p.trigger_evaluation
                    trig_fired_iso = (
                        te.trigger_bar_started_at.isoformat()
                        if te is not None and te.trigger_bar_started_at is not None
                        else None
                    )
                    trig_price_f = (
                        float(te.trigger_price)
                        if te is not None and te.trigger_price is not None
                        else None
                    )
                    _scanner_rows.append(ScannerRow(
                        symbol=r.symbol,
                        price=float(r.price) if r.price is not None else None,
                        change_percent=float(r.change_from_prior_close_percent) if r.change_from_prior_close_percent is not None else None,
                        gap_percent=float(r.gap_percent) if r.gap_percent is not None else None,
                        volume=r.volume,
                        avg_daily_volume=float(r.average_daily_volume) if r.average_daily_volume is not None else None,
                        daily_rvol=float(r.daily_relative_volume) if r.daily_relative_volume is not None else None,
                        short_term_rvol=float(r.short_term_relative_volume) if r.short_term_relative_volume is not None else None,
                        score=p.score,
                        stage=p.stage_tag.value,
                        primary_invalid_reason=p.primary_invalid_reason,
                        headline=r.headline,
                        catalyst_tag=r.catalyst_tag.value,
                        catalyst_age_seconds=sv.catalyst_age_seconds if sv else None,
                        vwap=None,  # filled below if available
                        ema_9=None,
                        ema_20=None,
                        pullback_retracement_pct=None,
                        float_shares=float(r.float_shares) if r.float_shares is not None else None,
                        sentiment_direction=verdict.direction.value if verdict else None,
                        observed_at=r.observed_at.isoformat(),
                        trigger_fired_at=trig_fired_iso,
                        trigger_price=trig_price_f,
                    ))
                # Enrich with context features where available
                for i, p in enumerate(projections):
                    sym = p.row.symbol
                    # Use enriched snapshot (has computed VWAP) instead of raw snapshot
                    snap = enriched_snapshots.get(sym) or snapshots.get(sym)
                    if snap:
                        try:
                            ctx = build_context_features(
                                snap,
                                bars_for_session(intraday_by_sym.get(sym, ()), as_of=now),
                            )
                            row = _scanner_rows[i]
                            _scanner_rows[i] = ScannerRow(
                                symbol=row.symbol, price=row.price, change_percent=row.change_percent,
                                gap_percent=row.gap_percent, volume=row.volume, avg_daily_volume=row.avg_daily_volume,
                                daily_rvol=row.daily_rvol, short_term_rvol=row.short_term_rvol,
                                score=row.score, stage=row.stage, primary_invalid_reason=row.primary_invalid_reason,
                                headline=row.headline, catalyst_tag=row.catalyst_tag,
                                catalyst_age_seconds=row.catalyst_age_seconds,
                                vwap=float(ctx.vwap) if ctx.vwap else None,
                                ema_9=float(ctx.ema_9) if ctx.ema_9 else None,
                                ema_20=float(ctx.ema_20) if ctx.ema_20 else None,
                                pullback_retracement_pct=float(ctx.pullback_retracement_percent) if ctx.pullback_retracement_percent else None,
                                float_shares=row.float_shares,
                                sentiment_direction=row.sentiment_direction,
                                observed_at=row.observed_at,
                                trigger_fired_at=row.trigger_fired_at,
                                trigger_price=row.trigger_price,
                            )
                        except Exception:
                            pass

                _scan_elapsed = (datetime.now(UTC) - scan_start).total_seconds()
                get_scanner_state().update(
                    _scanner_rows,
                    scan_duration=_scan_elapsed,
                    total_symbols=len(active_syms),
                )

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

                    # Gate constants (shared by Tier 0 and Tier 1)
                    MAX_TRIGGER_AGE_SEC = _STRATEGY_DEFAULTS.max_trigger_age_seconds
                    MAX_ENTRY_DRIFT_PCT = Decimal("0.0075")  # 0.75%
                    MIN_STOP_PCT = Decimal("0.005")       # stop must be ≥0.5% below entry
                    MAX_STOP_PCT = Decimal("0.05")        # stop must be ≤5%  below entry
                    TARGET_1_R = Decimal("1.5")
                    TARGET_2_R = Decimal("2.5")
                    CENT = Decimal("0.01")

                    async def _send_tg(text: str, *, log_label: str, sym: str = "") -> None:
                        try:
                            await _telegram_transport.async_send(TelegramTransportRequest(
                                chat_id=_startup_config.telegram.operator_chat_id,
                                text=text,
                            ))
                            logger.info("Telegram %s sent: %s", log_label, sym)
                        except Exception as tg_err:
                            logger.warning("Telegram %s send failed (%s): %s", log_label, sym, tg_err)

                    # ── Tier 0: Lifecycle updates on already-alerted setups ──
                    # For each active setup, check current price against stop/T1/T2 and
                    # emit follow-up messages instead of re-sending "NEW SETUP".
                    # Terminal states (t2_hit/stopped/invalidated/expired) mark closed_at.
                    invalid_by_sym = {p.row.symbol: p for p in invalid}
                    for sym, setup in list(_alerted_setups.items()):
                        if setup.is_closed:
                            continue  # already terminal, waiting on cooldown

                        snap = snapshots.get(sym)
                        current_price = snap.last_price if snap is not None else None
                        if current_price is not None:
                            setup.peak_price = (
                                current_price if setup.peak_price is None
                                else max(setup.peak_price, current_price)
                            )

                        # Terminal-state handler: emits outcome to learning store + logs it.
                        # Called once per transition to a terminal stage.
                        def _finalize_terminal(s: AlertedSetup = setup) -> None:
                            store = adaptive_scorer.outcome_store if adaptive_scorer else _outcome_store
                            _record_setup_outcome(s, outcome_store=store)

                        # 1. Invalidation (from projections)
                        inv_proj = invalid_by_sym.get(sym)
                        if inv_proj is not None and setup.stage in ("alerted", "t1_hit"):
                            reason = inv_proj.primary_invalid_reason or "setup_invalid"
                            setup.stage = "invalidated"
                            setup.closed_at = now
                            setup.invalidation_reason = reason
                            _finalize_terminal()
                            await _send_tg(
                                f"❌ <b>{sym} INVALIDATED</b>\n"
                                f"Reason: <code>{reason}</code>\n"
                                f"Entry was <code>${setup.entry_price}</code>",
                                log_label="invalidation", sym=sym,
                            )
                            continue

                        if current_price is not None:
                            # 2. Stopped out (check before T2 — downside wins ties)
                            if setup.stage in ("alerted", "t1_hit") and current_price <= setup.stop_price:
                                # r_mult depends on whether T1 was already hit (stop at entry)
                                r_mult = "breakeven" if setup.stage == "t1_hit" else "−1R"
                                setup.stage = "stopped"
                                setup.closed_at = now
                                _finalize_terminal()
                                await _send_tg(
                                    f"🛑 <b>{sym} STOPPED</b>\n"
                                    f"Exit: <code>${current_price.quantize(CENT)}</code>\n"
                                    f"Entry: <code>${setup.entry_price}</code>  ({r_mult})",
                                    log_label="stopped", sym=sym,
                                )
                                continue

                            # 3. T2 hit (full exit, terminal)
                            if setup.stage in ("alerted", "t1_hit") and current_price >= setup.target_2:
                                setup.stage = "t2_hit"
                                setup.closed_at = now
                                _finalize_terminal()
                                await _send_tg(
                                    f"🎯🎯 <b>{sym} T2 HIT — full exit</b>\n"
                                    f"Price: <code>${current_price.quantize(CENT)}</code>\n"
                                    f"Entry: <code>${setup.entry_price}</code>  (+2.5R)",
                                    log_label="t2_hit", sym=sym,
                                )
                                continue

                            # 4. T1 hit (not terminal — move stop to entry, still aim for T2)
                            if setup.stage == "alerted" and current_price >= setup.target_1:
                                setup.stage = "t1_hit"
                                await _send_tg(
                                    f"🎯 <b>{sym} T1 HIT — risk-free</b>\n"
                                    f"Price: <code>${current_price.quantize(CENT)}</code>\n"
                                    f"Move stop → <code>${setup.entry_price}</code> (breakeven)\n"
                                    f"Next target: <code>${setup.target_2}</code>",
                                    log_label="t1_hit", sym=sym,
                                )
                                continue

                        # 5. Expired (no T1 follow-through within window)
                        elapsed_since_fire = (now - setup.trigger_bar_started_at).total_seconds()
                        if setup.stage == "alerted" and elapsed_since_fire > _TRIGGER_EXPIRY_SEC:
                            setup.stage = "expired"
                            setup.closed_at = now
                            _finalize_terminal()
                            await _send_tg(
                                f"⌛ <b>{sym} expired</b>\n"
                                f"No T1 follow-through in {int(elapsed_since_fire / 60)}min\n"
                                f"Trigger fired @ <code>${setup.trigger_price}</code>",
                                log_label="expired", sym=sym,
                            )

                    # ── Tier 1: New-setup alerts ─────────────────────────────
                    # Gates: fresh trigger + not chasing + sane pullback stop.
                    # Dedup: at most one "NEW SETUP" per symbol until its prior
                    # setup closes and the cooldown expires.
                    for p in sorted(valid, key=lambda x: x.score, reverse=True)[:5]:
                        sym = p.row.symbol

                        # ── Dedup via lifecycle state ──────────────────────
                        existing = _alerted_setups.get(sym)
                        if existing is not None and not existing.is_closed:
                            continue  # active setup; let Tier 0 handle updates
                        if existing is not None and existing.is_closed:
                            elapsed_since_close = (now - existing.closed_at).total_seconds()
                            if elapsed_since_close < _REALERT_COOLDOWN_SEC:
                                continue  # cooldown
                            # Cooldown passed; only re-alert on a genuinely new trigger bar
                            trig_eval_check = p.trigger_evaluation
                            new_fire = trig_eval_check.trigger_bar_started_at if trig_eval_check else None
                            if new_fire is None or new_fire <= existing.trigger_bar_started_at:
                                continue

                        # ── Freshness gate ──────────────────────────────────────
                        trig_eval = p.trigger_evaluation
                        trig_fire_price = trig_eval.trigger_price if trig_eval else None
                        trig_fired_at = trig_eval.trigger_bar_started_at if trig_eval else None
                        fired_ago_sec: int | None = None
                        if trig_fired_at is not None:
                            fired_ago_sec = int((now - trig_fired_at).total_seconds())
                            if fired_ago_sec > MAX_TRIGGER_AGE_SEC:
                                logger.info(
                                    "Telegram skip: %s trigger stale (%ds > %ds)",
                                    sym, fired_ago_sec, MAX_TRIGGER_AGE_SEC,
                                )
                                continue

                        # ── Distance gate (don't chase) ─────────────────────────
                        entry_price = p.row.price
                        if entry_price is None:
                            continue
                        if trig_fire_price is not None and trig_fire_price > 0:
                            drift = (entry_price - trig_fire_price) / trig_fire_price
                            if drift > MAX_ENTRY_DRIFT_PCT:
                                logger.info(
                                    "Telegram skip: %s price drifted %.2f%% above trigger (entry=%s fire=%s)",
                                    sym, float(drift) * 100, entry_price, trig_fire_price,
                                )
                                continue

                        # ── Stop sanity (pullback-low must be plausible) ────────
                        stop_price: Decimal | None = None
                        if p.invalidation is None or not p.invalidation.invalidated:
                            sym_snapshot = snapshots.get(sym)
                            if sym_snapshot is not None:
                                ctx = build_context_features(
                                    sym_snapshot,
                                    intraday_bars=intraday_by_sym.get(sym, ()),
                                )
                                if ctx.pullback_low is not None:
                                    lo_bound = (entry_price * (Decimal("1") - MAX_STOP_PCT))
                                    hi_bound = (entry_price * (Decimal("1") - MIN_STOP_PCT))
                                    if lo_bound <= ctx.pullback_low <= hi_bound:
                                        stop_price = ctx.pullback_low.quantize(CENT)
                        if stop_price is None:
                            # No sane stop → don't fire an alert we can't trade.
                            # TODO: replace min(lows) with actual pullback-candle detection
                            # (Ross Cameron rule) in scanner/context_features.py
                            logger.info(
                                "Telegram skip: %s no sane pullback-low stop (entry=%s)",
                                sym, entry_price,
                            )
                            continue

                        # ── Targets + real R:R ──────────────────────────────────
                        risk = entry_price - stop_price
                        if risk <= 0:
                            continue
                        target_1 = (entry_price + risk * TARGET_1_R).quantize(CENT)
                        target_2 = (entry_price + risk * TARGET_2_R).quantize(CENT)
                        rr_value = (target_1 - entry_price) / risk  # real, not hardcoded
                        rr_ratio = f"R:R  1:{rr_value:.2f}"
                        risk_per_share = f"Risk ${risk.quantize(CENT)}/share"

                        agent_review: TradingAgentsReviewResult | None = None
                        if (
                            agent_reviewer is not None
                            and p.stage_tag.value == "trigger_ready"
                            and p.score >= config.agent_review.min_score
                        ):
                            agent_review = await _run_agent_review(
                                agent_reviewer,
                                agent_review_store,
                                symbol=sym,
                                trade_date=now.date().isoformat(),
                                timeout_seconds=config.agent_review.timeout_seconds,
                                context={
                                    "stage": p.stage_tag.value,
                                    "score": p.score,
                                    "headline": p.row.headline,
                                    "catalyst_tag": p.row.catalyst_tag.value,
                                    "daily_rvol": str(p.row.daily_relative_volume)
                                    if p.row.daily_relative_volume is not None
                                    else None,
                                    "change_percent": str(p.row.change_from_prior_close_percent)
                                    if p.row.change_from_prior_close_percent is not None
                                    else None,
                                },
                            )

                        # Committed to send — record the setup for Tier-0 lifecycle tracking.
                        # Snapshot entry-time features so when the setup hits a terminal
                        # state we can record a full OutcomeRecord for the learning layer.
                        sentiment = sentiment_verdicts.get(sym)
                        _alerted_setups[sym] = AlertedSetup(
                            symbol=sym,
                            first_alerted_at=now,
                            trigger_price=(trig_fire_price or entry_price).quantize(CENT),
                            entry_price=entry_price.quantize(CENT),
                            stop_price=stop_price,
                            target_1=target_1,
                            target_2=target_2,
                            trigger_bar_started_at=trig_fired_at or now,
                            catalyst_tag=p.row.catalyst_tag.value,
                            catalyst_quality=sentiment.catalyst_quality.value if sentiment else None,
                            sentiment_direction=sentiment.direction.value if sentiment else None,
                            sentiment_confidence=sentiment.confidence if sentiment else None,
                            agent_review_status=agent_review.status if agent_review else None,
                            agent_review_decision=(
                                _agent_review_plain_text(agent_review, limit=500)
                                if agent_review
                                else None
                            ),
                            agent_review_error=agent_review.error if agent_review else None,
                            score_at_entry=p.score,
                            daily_rvol=p.row.daily_relative_volume,
                            short_term_rvol=p.row.short_term_relative_volume,
                            change_percent=p.row.change_from_prior_close_percent,
                            gap_percent=p.row.gap_percent,
                        )
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

                        catalyst_label = p.row.catalyst_tag.value.replace("_", " ").title()
                        chg = ""
                        if p.row.change_from_prior_close_percent is not None:
                            chg = f"↑{p.row.change_from_prior_close_percent:.1f}%"

                        # Freshness line ("fired 42s ago @ $17.18")
                        freshness_line = ""
                        if fired_ago_sec is not None and trig_fire_price is not None:
                            freshness_line = (
                                f"⚡ fired {fired_ago_sec}s ago @ "
                                f"<code>${trig_fire_price.quantize(CENT)}</code>"
                            )
                        elif fired_ago_sec is not None:
                            freshness_line = f"⚡ fired {fired_ago_sec}s ago"

                        lines = [
                            f"🔔 <b>NEW SETUP — {sym}</b>",
                            "",
                            f"🟢 BUY  │  score {p.score}/100  │  {stage_icon} {stage_label}{sent_dot}",
                        ]
                        if freshness_line:
                            lines.append(freshness_line)
                        lines.append("")
                        lines.append(f"Entry:    <code>${entry_price.quantize(CENT)}</code>")
                        lines.append(f"Stop:     <code>${stop_price}</code>  🛑")
                        lines.append(f"Target₁:  <code>${target_1}</code>  🎯")
                        lines.append(f"Target₂:  <code>${target_2}</code>  🎯")
                        lines.append("")
                        lines.append(f"{rr_ratio}  │  {risk_per_share}")

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

                        if agent_review is not None:
                            lines.append("")
                            lines.append("🤖 <b>AI Agent Review</b>")
                            review_label = "Decision" if agent_review.status == "ok" else agent_review.status.title()
                            lines.append(f"{review_label}: {_agent_review_text(agent_review)}")
                        elif agent_reviewer is not None and p.stage_tag.value == "trigger_ready":
                            lines.append("")
                            lines.append("🤖 <b>AI Agent Review</b>")
                            lines.append("Skipped: score below configured review threshold")

                        await _send_tg(
                            "\n".join(lines),
                            log_label=f"new_setup score={p.score}",
                            sym=sym,
                        )

                    # ── Publish lifecycle state for the dashboard hero panel ──
                    # Active setups + recently-closed ones (purged after cooldown).
                    # Prune anything older than the re-alert cooldown so the panel
                    # doesn't pile up stale closed rows.
                    for stale_sym, stale_setup in list(_alerted_setups.items()):
                        if (
                            stale_setup.is_closed
                            and stale_setup.closed_at is not None
                            and (now - stale_setup.closed_at).total_seconds() > _REALERT_COOLDOWN_SEC
                        ):
                            _alerted_setups.pop(stale_sym, None)
                    get_alerted_setups_state().replace(list(_alerted_setups.values()))

                    # ── Tier 1b: Building watchlist ─────────────────────────
                    # These are not trade alerts: no stop/target lifecycle, no
                    # approval buttons. They mirror the dashboard's building tab.
                    top_building = sorted(building, key=lambda x: x.score, reverse=True)[:5]
                    building_digest = tuple((bp.row.symbol, bp.score) for bp in top_building)
                    if top_building and (
                        building_digest != _last_building_digest or _tick_count % 5 == 0
                    ):
                        building_lines = [
                            f"🔨 <b>BUILDING SETUPS</b> — {now.strftime('%H:%M:%S UTC')}  │  {elapsed:.1f}s",
                            "",
                            f"{len(building)} building  │  {len(triggered)} actionable  │  {len(invalid)} invalid",
                            "",
                        ]
                        for bp in top_building:
                            price_text = (
                                f"${bp.row.price.quantize(CENT)}"
                                if bp.row.price is not None
                                else "$--"
                            )
                            stats = []
                            if bp.row.change_from_prior_close_percent is not None:
                                stats.append(f"↑{bp.row.change_from_prior_close_percent:.1f}%")
                            if bp.row.gap_percent is not None:
                                stats.append(f"gap {bp.row.gap_percent:.1f}%")
                            if bp.row.daily_relative_volume is not None:
                                stats.append(f"RVOL {bp.row.daily_relative_volume:.1f}x")
                            catalyst_label = bp.row.catalyst_tag.value.replace("_", " " ).title()
                            stat_text = "  │  ".join(stats) if stats else "watching"
                            building_lines.append(
                                f"• <b>{bp.row.symbol}</b>  {price_text}  score {bp.score}  │  {stat_text}  │  {catalyst_label}"
                            )
                        building_lines.extend([
                            "",
                            "<i>Watchlist only — not a buy alert yet.</i>",
                        ])
                        await _send_tg(
                            "\n".join(building_lines),
                            log_label="building_watchlist",
                        )
                        _last_building_digest = building_digest
                    elif not top_building and _last_building_digest:
                        _last_building_digest = ()

                    # ── Tier 2: Periodic scan summary (every 5th tick) ──
                    if not valid and _tick_count % 5 == 0 and projections:
                        summary_lines = [
                            f"📊 <b>SCAN</b> — {now.strftime('%H:%M:%S UTC')}  │  {elapsed:.1f}s",
                            "",
                            f"⚡ {len(triggered)} actionable  │  🔨 {len(building)} building  │  ❌ {len(invalid)} invalid",
                        ]
                        invalid_reasons = Counter(p.primary_invalid_reason or "unknown" for p in invalid)
                        if invalid_reasons:
                            reason_text = ", ".join(
                                f"{reason} {count}"
                                for reason, count in invalid_reasons.most_common(3)
                            )
                            summary_lines.append(f"Reasons: {reason_text}")
                        source_text = (
                            f"Sources: {len(mover_syms)} movers, "
                            f"{len([s for s in active_syms if s not in mover_syms])} Benzinga-only"
                        )
                        summary_lines.append(source_text)
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
                            await _telegram_transport.async_send(TelegramTransportRequest(
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
                            await _telegram_transport.async_send(TelegramTransportRequest(
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
if _startup_config.llm.is_configured:
    _sentiment_analyzer = SentimentAnalyzer(
        api_key=_startup_config.llm.api_key,  # type: ignore[arg-type]
        base_url=_startup_config.llm.base_url,
        model=_startup_config.llm.model,
        temperature=_startup_config.llm.temperature,
    )
    logger.info("Intelligence: LLM sentiment analyzer enabled (model=%s, provider=%s)", _startup_config.llm.model, _startup_config.llm.base_url)
else:
    logger.info("Intelligence: LLM sentiment analyzer disabled (no GROQ_API_KEY or OPENAI_API_KEY)")

_outcome_store = OutcomeStore()
_adaptive_scorer = AdaptiveScorer(_outcome_store)
logger.info("Intelligence: adaptive learning layer enabled (store=%s)", _outcome_store.path)

_agent_reviewer: TradingAgentsReviewer | None = None
_agent_review_store: TradingAgentsReviewStore | None = None
if _startup_config.agent_review.enabled:
    _agent_reviewer = TradingAgentsReviewer(TradingAgentsReviewConfig.from_env(os.environ))
    _agent_review_store = TradingAgentsReviewStore()
    logger.info(
        "TradingAgents: review layer enabled (provider=%s model=%s min_score=%d cap=%d)",
        _agent_reviewer.config.llm_provider,
        _agent_reviewer.config.deep_model,
        _startup_config.agent_review.min_score,
        _agent_reviewer.config.max_reviews_per_day,
    )
else:
    logger.info("TradingAgents: review layer disabled (set TRADINGAGENTS_REVIEW_ENABLED=true)")

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
                receipt = await _telegram_transport.async_send(TelegramTransportRequest(
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
                agent_reviewer=_agent_reviewer,
                agent_review_store=_agent_review_store,
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
