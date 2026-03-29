"""
stream_scanner.py — event-driven scanner using Alpaca WebSocket streams

Architecture:
  - Alpaca NewsDataStream  → instant news detection (Benzinga data)
  - Alpaca StockDataStream → real-time 1-minute bars for ALL symbols
  - Two-stage alerts:
      Stage 1: news arrives → quick quote check → "heads up" in <2s
      Stage 2: bars accumulate → full signal chain → scored alert in <10s
  - Finnhub peers still used for sector expansion (cached, low rate usage)
  - yfinance screener for Layer 3 top movers (periodic, every 5 min)

Usage (from backend/):
    export $(cat .env | xargs) && uv run python stream_scanner.py
"""
from __future__ import annotations

import asyncio
import math
import os
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import aiohttp

from alpaca.data.live import StockDataStream, NewsDataStream
from alpaca.data.enums import DataFeed
from alpaca.data.models import Bar as AlpacaBar
from alpaca.data.models.news import News as AlpacaNews

from app.config import AppConfig
from app.providers.models import (
    DailyBar,
    IntradayBar,
    MarketSnapshot,
)
from app.scanner.context_features import build_context_features
from app.scanner.invalidation import evaluate_invalidation
from app.scanner.metrics import build_market_metrics
from app.scanner.news_linking import latest_news_by_symbol
from app.scanner.row_builder import build_candidate_row
from app.scanner.setup_validity import evaluate_setup_validity
from app.scanner.strategy_projection import StrategyProjection, project_strategy_row
from app.scanner.trigger_logic import evaluate_first_break_trigger
from app.scanner.trigger_policy import resolve_trigger_bars

# ── tunables ──────────────────────────────────────────────────────────────────
LOOKBACK_DAYS      = 20
MAX_BAR_HISTORY    = 400    # max 1m bars to keep per symbol (~6.5h session)
DEEP_SCAN_DELAY    = 3.0    # seconds after news before running deep scan
MOVERS_INTERVAL    = 300    # run yfinance movers screener every 5 min
FINNHUB_BASE       = "https://finnhub.io/api/v1"
PEER_CACHE_TTL     = 86400  # 24 hours
PEER_BUDGET        = 5      # max peer lookups per news event
# ─────────────────────────────────────────────────────────────────────────────


# ── In-memory state ──────────────────────────────────────────────────────────

class ScannerState:
    """Shared mutable state for the event-driven scanner."""

    def __init__(self) -> None:
        # Latest bar data per symbol: symbol → list of IntradayBar (most recent last)
        self.bars: dict[str, list[IntradayBar]] = defaultdict(list)
        # Latest snapshot per symbol (built from most recent bar)
        self.snapshots: dict[str, MarketSnapshot] = {}
        # News events: symbol → NewsEvent (from Benzinga via Alpaca)
        self.news_headlines: dict[str, dict[str, Any]] = {}
        # Peer cache: symbol → (peers, epoch)
        self.peer_cache: dict[str, tuple[list[str], float]] = {}
        # Active projections for display
        self.projections: list[StrategyProjection] = []
        # Symbols we're actively watching
        self.active_symbols: set[str] = set()
        # Timestamps
        self.last_movers_check = 0.0
        self.scan_count = 0

    def add_bar(self, symbol: str, bar: IntradayBar) -> None:
        bars = self.bars[symbol]
        bars.append(bar)
        # Trim to max history
        if len(bars) > MAX_BAR_HISTORY:
            self.bars[symbol] = bars[-MAX_BAR_HISTORY:]

    def get_bars(self, symbol: str) -> tuple[IntradayBar, ...]:
        return tuple(self.bars.get(symbol, []))

    def update_snapshot(self, symbol: str, bar: IntradayBar) -> None:
        """Build a MarketSnapshot from the latest bar."""
        now = datetime.now(UTC)
        bars = self.bars.get(symbol, [])
        if not bars:
            return

        # Find session open and high/low from all bars today
        today_bars = [b for b in bars if b.start_at.date() == now.date()]
        if not today_bars:
            today_bars = bars[-60:]  # fallback: last hour

        high = max(float(b.high_price) for b in today_bars)
        low = min(float(b.low_price) for b in today_bars)
        open_price = float(today_bars[0].open_price) if today_bars else float(bar.open_price)
        volume = sum(b.volume for b in today_bars)

        self.snapshots[symbol] = MarketSnapshot(
            symbol=symbol,
            provider="alpaca",
            observed_at=bar.start_at,
            received_at=now,
            last_price=bar.close_price,
            session_volume=volume,
            previous_close=None,  # filled from first bar of day if available
            open_price=str(open_price),
            high_price=str(high),
            low_price=str(low),
        )


state = ScannerState()


# ── Display helpers ──────────────────────────────────────────────────────────

_STAGE_ICON = {
    "building":      "🔨",
    "trigger_ready": "⚡",
    "invalidated":   "❌",
}


def _fmt(value, suffix="", d=2):
    if value is None:
        return "n/a"
    return f"{float(value):.{d}f}{suffix}"


def print_projection(rank: int, proj: StrategyProjection) -> None:
    row = proj.row
    icon = _STAGE_ICON.get(proj.stage_tag.value, "?")
    real_reason = proj.primary_invalid_reason
    if (
        real_reason == "setup_invalid"
        and proj.setup_validity.primary_invalid_reason is not None
    ):
        real_reason = proj.setup_validity.primary_invalid_reason.value
    reason = f" reason={real_reason}" if real_reason else ""
    print(
        f"  #{rank:<2}  {row.symbol:<6}  "
        f"${_fmt(row.price)}  "
        f"chg={_fmt(row.change_from_prior_close_percent, '%')}  "
        f"rvol={_fmt(row.daily_relative_volume, 'x')}  "
        f"pullback={_fmt(row.pullback_from_high_percent, '%')}  "
        f"age={int(row.time_since_news_seconds // 60)}m  "
        f"score={proj.score:>3}  {icon} {proj.stage_tag.value}{reason}"
    )
    print(f"         └─ {row.headline[:80]}")


# ── Finnhub peer expansion (reused from scan_runner) ─────────────────────────

async def finnhub_peers(
    session: aiohttp.ClientSession,
    symbol: str,
    api_key: str,
) -> list[str]:
    now_ts = time.time()
    if symbol in state.peer_cache:
        peers, cached_at = state.peer_cache[symbol]
        if now_ts - cached_at < PEER_CACHE_TTL:
            return peers
    if not api_key:
        return []
    try:
        async with session.get(
            f"{FINNHUB_BASE}/stock/peers",
            params={"symbol": symbol, "token": api_key},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            peers = [p for p in data if isinstance(p, str) and p != symbol]
            state.peer_cache[symbol] = (peers, now_ts)
            return peers
    except Exception:
        return []


# ── Signal chain (runs on a single symbol) ───────────────────────────────────

def evaluate_symbol(symbol: str) -> StrategyProjection | None:
    """Run the full signal chain for one symbol. Returns None if no data."""
    snapshot = state.snapshots.get(symbol)
    news_data = state.news_headlines.get(symbol)
    if snapshot is None or news_data is None:
        return None

    # Build a minimal NewsEvent-like object for the signal chain
    from app.providers.models import NewsEvent, ProviderCapability
    try:
        news_event = NewsEvent(
            provider="alpaca",
            capability=ProviderCapability.NEWS,
            event_id=news_data.get("id", ""),
            headline=news_data.get("headline", ""),
            symbols=(symbol,),
            published_at=news_data.get("published_at", datetime.now(UTC)),
            received_at=datetime.now(UTC),
            source=news_data.get("source", "benzinga"),
            url=news_data.get("url"),
            body=news_data.get("summary"),
        )
    except Exception:
        return None

    # Metrics
    metrics = build_market_metrics(
        snapshot,
        daily_bars=(),
        current_bar=None,
        historical_intraday_bars=(),
        lookback_days=LOOKBACK_DAYS,
    )
    row = build_candidate_row(snapshot, news_event, metrics)
    if row is None:
        return None

    # Context → validity → trigger → invalidation → projection
    intraday = state.get_bars(symbol)
    context = build_context_features(snapshot, intraday_bars=intraday)
    validity = evaluate_setup_validity(row, news_event, context)
    trigger_sel = resolve_trigger_bars(preferred_bars=(), fallback_bars=intraday)
    trigger = evaluate_first_break_trigger(trigger_sel)
    invalidation = evaluate_invalidation(
        row, news_event, context, setup_validity=validity,
    )
    return project_strategy_row(
        row,
        context_features=context,
        setup_validity=validity,
        trigger_evaluation=trigger,
        invalidation=invalidation,
    )


def run_scan_and_display() -> None:
    """Re-evaluate all active symbols and display results."""
    state.scan_count += 1
    now = datetime.now(UTC)
    projections: list[StrategyProjection] = []

    for symbol in list(state.active_symbols):
        proj = evaluate_symbol(symbol)
        if proj is not None:
            projections.append(proj)

    state.projections = projections

    if not projections:
        return

    projections.sort(key=lambda p: (not p.is_valid, -p.score))
    valid = [p for p in projections if p.is_valid]
    invalid = [p for p in projections if not p.is_valid]

    print(f"\n  {'─'*76}")
    print(f"  [{now.strftime('%H:%M:%S')}] {len(valid)} valid  |  "
          f"{len(invalid)} invalid  |  {len(projections)} total  |  "
          f"{len(state.active_symbols)} watching")
    print(f"  {'─'*76}")

    if valid:
        print(f"  ✅ VALID SETUPS:")
        for i, proj in enumerate(valid, 1):
            print_projection(i, proj)

    show_invalid = invalid[:5]
    if show_invalid:
        print(f"  ⚠️  TOP INVALID ({len(invalid)} total):")
        for i, proj in enumerate(show_invalid, 1):
            print_projection(i, proj)


# ── Alpaca event handlers ────────────────────────────────────────────────────

_eval_queue: asyncio.Queue[str] = asyncio.Queue()
_http_session: aiohttp.ClientSession | None = None
_finnhub_key: str = ""


async def on_news(news: AlpacaNews) -> None:
    """Called instantly when Alpaca pushes a news event."""
    now = datetime.now(UTC)
    symbols = [s for s in (news.symbols or []) if s and len(s) <= 5]

    if not symbols:
        return

    headline = news.headline or ""
    print(f"\n  ⚡ NEWS [{now.strftime('%H:%M:%S')}] {', '.join(symbols[:5])}: {headline[:70]}")

    for sym in symbols[:10]:
        state.news_headlines[sym] = {
            "id": str(news.id) if news.id else "",
            "headline": headline,
            "published_at": news.created_at or now,
            "source": news.source or "benzinga",
            "url": str(news.url) if news.url else None,
            "summary": news.summary if hasattr(news, "summary") else None,
        }
        state.active_symbols.add(sym)

        # Quick evaluation if we have bar data
        proj = evaluate_symbol(sym)
        if proj and proj.is_valid:
            print(f"  ✅ {sym} score={proj.score} {proj.stage_tag.value}")

    # Schedule deep scan after a delay (let bars arrive)
    for sym in symbols[:10]:
        await _eval_queue.put(sym)

    # Expand with peers (background, don't block)
    if _http_session and _finnhub_key:
        for sym in symbols[:3]:
            peers = await finnhub_peers(_http_session, sym, _finnhub_key)
            for peer in peers[:5]:
                state.active_symbols.add(peer)


async def on_bar(bar: AlpacaBar) -> None:
    """Called when a new 1-minute bar arrives from Alpaca."""
    symbol = bar.symbol
    if not symbol:
        return

    now = datetime.now(UTC)
    try:
        intraday_bar = IntradayBar(
            symbol=symbol,
            provider="alpaca",
            start_at=bar.timestamp.replace(tzinfo=UTC) if bar.timestamp.tzinfo is None else bar.timestamp,
            open_price=str(bar.open),
            high_price=str(bar.high),
            low_price=str(bar.low),
            close_price=str(bar.close),
            volume=int(bar.volume) if bar.volume else 0,
            interval_minutes=1,
        )
    except Exception:
        return

    state.add_bar(symbol, intraday_bar)
    state.update_snapshot(symbol, intraday_bar)

    # If this symbol has news, queue for evaluation
    if symbol in state.news_headlines:
        state.active_symbols.add(symbol)


# ── Background tasks ─────────────────────────────────────────────────────────

async def deep_scan_worker() -> None:
    """Process symbols queued for deep evaluation after news arrives."""
    while True:
        sym = await _eval_queue.get()
        try:
            # Wait for bars to arrive
            await asyncio.sleep(DEEP_SCAN_DELAY)
            proj = evaluate_symbol(sym)
            if proj:
                icon = _STAGE_ICON.get(proj.stage_tag.value, "?")
                reason = ""
                if proj.primary_invalid_reason:
                    real = proj.primary_invalid_reason
                    if real == "setup_invalid" and proj.setup_validity.primary_invalid_reason:
                        real = proj.setup_validity.primary_invalid_reason.value
                    reason = f" ({real})"
                print(f"  📊 DEEP: {sym} score={proj.score} {icon} {proj.stage_tag.value}{reason}")
        except Exception as exc:
            print(f"  [WARN] deep scan {sym}: {exc}")
        _eval_queue.task_done()


async def periodic_full_scan() -> None:
    """Run a full display scan every 30 seconds for active symbols."""
    while True:
        await asyncio.sleep(30)
        if state.active_symbols:
            run_scan_and_display()


async def periodic_movers_check() -> None:
    """Check yfinance top movers every 5 minutes."""
    import yfinance as yf

    while True:
        await asyncio.sleep(MOVERS_INTERVAL)
        now = time.time()
        try:
            loop = asyncio.get_event_loop()

            def _fetch():
                try:
                    from yfinance import EquityQuery
                    q = EquityQuery("and", [
                        EquityQuery("gt", ["percentchange", 3]),
                        EquityQuery("eq", ["region", "us"]),
                        EquityQuery("lt", ["intradaymarketcap", 2_000_000_000]),
                        EquityQuery("gte", ["intradayprice", 1]),
                        EquityQuery("gt", ["dayvolume", 50_000]),
                        EquityQuery("is-in", ["exchange", "NMS", "NYQ"]),
                    ])
                    result = yf.screen(q, sortField="percentchange", sortAsc=False, size=15)
                    return [r["symbol"] for r in result.get("quotes", []) if "symbol" in r]
                except Exception:
                    return []

            movers = await loop.run_in_executor(None, _fetch)
            if movers:
                new = [s for s in movers if s not in state.active_symbols]
                if new:
                    print(f"\n  📈 MOVERS: +{len(new)} new small-cap movers: {', '.join(new[:8])}")
                    state.active_symbols.update(new)
            state.last_movers_check = now
        except Exception:
            pass


# ── Main entry point ─────────────────────────────────────────────────────────

async def main() -> None:
    global _http_session, _finnhub_key

    alpaca_key = os.environ.get("ALPACA_API_KEY", "")
    alpaca_secret = os.environ.get("ALPACA_API_SECRET", "")
    _finnhub_key = os.environ.get("FINNHUB_API_KEY", "")

    if not alpaca_key or not alpaca_secret:
        print("ERROR: ALPACA_API_KEY and ALPACA_API_SECRET must be set.")
        print("  export $(cat .env | xargs)")
        sys.exit(1)

    print("=" * 80)
    print("  Buy Signal — Event-Driven Stream Scanner")
    print("=" * 80)
    print(f"  News     : Alpaca WebSocket (Benzinga, real-time push)")
    print(f"  Bars     : Alpaca WebSocket (IEX, all symbols, 1m)")
    print(f"  Peers    : Finnhub /stock/peers (cached 24h)")
    print(f"  Movers   : yfinance screener (every {MOVERS_INTERVAL}s)")
    print(f"  Mode     : event-driven — no polling, reacts in <2s")
    print()
    print("  Waiting for news and bar events …")
    print()

    # HTTP session for Finnhub peers
    _http_session = aiohttp.ClientSession()

    # Start background workers
    asyncio.create_task(deep_scan_worker())
    asyncio.create_task(periodic_full_scan())
    asyncio.create_task(periodic_movers_check())

    # Alpaca news stream
    news_stream = NewsDataStream(alpaca_key, alpaca_secret)
    news_stream.subscribe_news(on_news, "*")

    # Alpaca bar stream (all symbols via wildcard)
    bar_stream = StockDataStream(alpaca_key, alpaca_secret, feed=DataFeed.IEX)
    bar_stream.subscribe_bars(on_bar, "*")

    print("  Connecting to Alpaca streams …")

    # _run_forever() is an async coroutine — run both in the same event loop
    try:
        await asyncio.gather(
            news_stream._run_forever(),
            bar_stream._run_forever(),
        )
    except KeyboardInterrupt:
        print("\n  Shutting down …")
    finally:
        await _http_session.close()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="  [%(name)s] %(message)s")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  Stopped.")
