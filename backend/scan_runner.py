"""
scan_runner.py — live scanner loop

Data sources:
  - Benzinga  → news / catalyst detection (XML API, free)
  - Finnhub   → real-time quote per symbol (free, 60 req/min)
  - Polygon   → 20-day daily bar history for ADV/RVOL (free plan, EOD)

Usage (from backend/):
    export $(cat .env | xargs) && python scan_runner.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Mapping

import aiohttp
import yfinance as yf

from app.config import AppConfig
from app.providers.benzinga_adapter import BenzingaNewsProvider
from app.providers.models import (
    DailyBar,
    IntradayBar,
    MarketSnapshot,
    ProviderCapability,
    ProviderHealthSnapshot,
    ProviderHealthState,
    ProviderBatch,
)
from app.providers.polygon_adapter import PolygonSnapshotProvider
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
NEWS_LIMIT        = 100
LOOKBACK_DAYS     = 20
POLL_INTERVAL_SEC = 60
MIN_CHANGE_PCT    = 2.0   # min % change from prior close to surface
MAX_SYMBOLS       = 40    # cap to stay well within Finnhub 60 req/min free limit
# ─────────────────────────────────────────────────────────────────────────────

SEED_SYMBOLS = [
    "AAPL","TSLA","NVDA","AMD","META","AMZN","MSFT","GOOGL","NFLX",
    "COIN","SOUN","MARA","RIOT","PLTR","SOFI","NIO","RIVN","SMCI",
    "ARM","HOOD","RBLX","SNAP","UBER","LCID","CRWD","APLD","IONQ",
    "INTC","MU","NET","SHOP","TSM","ADBE","PATH","CORZ","IREN",
]

FINNHUB_BASE = "https://finnhub.io/api/v1"


# ── Benzinga XML parsing ──────────────────────────────────────────────────────

def _xml_item_to_dict(item: ET.Element) -> dict[str, Any]:
    stocks = []
    stocks_el = item.find("stocks")
    if stocks_el is not None:
        for s in stocks_el.findall("item"):
            name_el = s.find("name")
            if name_el is not None and (name_el.text or "").strip():
                stocks.append({"name": (name_el.text or "").strip()})

    channels = []
    channels_el = item.find("channels")
    if channels_el is not None:
        for c in channels_el.findall("item"):
            name_el = c.find("name")
            if name_el is not None and (name_el.text or "").strip():
                channels.append({"name": (name_el.text or "").strip()})

    return {
        "id":       (item.findtext("id") or "").strip(),
        "author":   (item.findtext("author") or "").strip(),
        "created":  (item.findtext("created") or "").strip(),
        "updated":  (item.findtext("updated") or "").strip(),
        "title":    (item.findtext("title") or "").strip(),
        "body":     (item.findtext("body") or "").strip() or None,
        "url":      (item.findtext("url") or "").strip() or None,
        "stocks":   stocks,
        "channels": channels,
    }


def _parse_benzinga_xml(raw: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(raw)
    return [_xml_item_to_dict(item) for item in root.findall("item")]


# ── HTTP fetchers ─────────────────────────────────────────────────────────────

def make_benzinga_fetcher(session: aiohttp.ClientSession):
    async def fetch_json(url: str, params: Mapping[str, Any]) -> Any:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            resp.raise_for_status()
            return _parse_benzinga_xml(await resp.read())
    return fetch_json


def make_polygon_fetcher(session: aiohttp.ClientSession):
    async def fetch_json(url: str, params: Mapping[str, Any]) -> Any:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)
    return fetch_json


# ── Finnhub: real-time quotes ─────────────────────────────────────────────────

async def finnhub_quote(
    session: aiohttp.ClientSession,
    symbol: str,
    api_key: str,
) -> dict[str, Any] | None:
    """Fetch a single Finnhub /quote. Returns None on error."""
    try:
        async with session.get(
            f"{FINNHUB_BASE}/quote",
            params={"symbol": symbol, "token": api_key},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            # c=current, h=high, l=low, o=open, pc=prev_close, t=timestamp
            if not data.get("c"):
                return None
            return data
    except Exception:
        return None


async def fetch_finnhub_quotes(
    session: aiohttp.ClientSession,
    symbols: list[str],
    api_key: str,
    now: datetime,
) -> dict[str, MarketSnapshot]:
    """
    Fetch Finnhub /quote for each symbol concurrently (rate-limited).
    Returns a dict of symbol → MarketSnapshot.
    """
    # Finnhub free: 60 req/min. Batch with a small delay to be safe.
    BATCH = 20
    results: dict[str, MarketSnapshot] = {}

    for i in range(0, len(symbols), BATCH):
        batch = symbols[i : i + BATCH]
        quotes = await asyncio.gather(*[finnhub_quote(session, sym, api_key) for sym in batch])
        for sym, q in zip(batch, quotes):
            if q is None:
                continue
            try:
                snap = MarketSnapshot(
                    symbol=sym,
                    provider="finnhub",
                    observed_at=datetime.fromtimestamp(q["t"], tz=UTC) if q.get("t") else now,
                    received_at=now,
                    last_price=str(q["c"]),
                    session_volume=0,          # Finnhub /quote doesn't include volume
                    previous_close=str(q["pc"]) if q.get("pc") else None,
                    open_price=str(q["o"]) if q.get("o") else None,
                    high_price=str(q["h"]) if q.get("h") else None,
                    low_price=str(q["l"]) if q.get("l") else None,
                )
                results[sym] = snap
            except Exception:
                continue

        if i + BATCH < len(symbols):
            await asyncio.sleep(1.0)   # small pause between batches

    return results


# ── Polygon: daily OHLCV bars for ADV/RVOL ───────────────────────────────────

async def fetch_polygon_daily_bars(
    polygon: PolygonSnapshotProvider,
    symbols: list[str],
    lookback_days: int,
) -> tuple[DailyBar, ...]:
    """
    Fetch historical daily bars from Polygon (works on free plan).
    Used only for ADV / daily RVOL computation.
    Returns empty tuple on any error.
    """
    try:
        batch = await polygon.fetch_daily_bars(symbols, lookback_days=lookback_days)
        return batch.records
    except Exception as exc:
        print(f"  [WARN] Polygon daily bars failed: {exc} — RVOL will show n/a")
        return ()

# ── yfinance: intraday 1m bars ───────────────────────────────────────────────

def fetch_intraday_bars_yf(symbols: list[str]) -> dict[str, tuple[IntradayBar, ...]]:
    """
    Fetch 1-minute intraday bars for each symbol using yfinance (free, no key).
    Returns dict of symbol → tuple of IntradayBar.
    Today + last session (period=2d) so we always have bars even post-close.
    """
    if not symbols:
        return {}
    try:
        tickers = " ".join(symbols)
        raw = yf.download(tickers, period="2d", interval="1m", progress=False, group_by="ticker")
    except Exception as exc:
        print(f"  [WARN] yfinance download failed: {exc}")
        return {}

    result: dict[str, tuple[IntradayBar, ...]] = {}
    for sym in symbols:
        try:
            # yfinance returns MultiIndex when multiple tickers
            if len(symbols) == 1:
                df = raw
            else:
                df = raw[sym] if sym in raw.columns.get_level_values(0) else None
            if df is None or df.empty:
                continue
            # Flatten MultiIndex columns if needed
            if hasattr(df.columns, "levels"):
                df.columns = df.columns.get_level_values(-1)
            bars = []
            for ts, row in df.iterrows():
                try:
                    bar = IntradayBar(
                        symbol=sym,
                        provider="yfinance",
                        start_at=ts.to_pydatetime().astimezone(UTC),
                        open_price=str(row["Open"]) if row["Open"] and not __import__("math").isnan(float(row["Open"])) else "0",
                        high_price=str(row["High"]) if row["High"] and not __import__("math").isnan(float(row["High"])) else "0",
                        low_price=str(row["Low"]) if row["Low"] and not __import__("math").isnan(float(row["Low"])) else "0",
                        close_price=str(row["Close"]) if row["Close"] and not __import__("math").isnan(float(row["Close"])) else "0",
                        volume=int(row["Volume"]) if row["Volume"] and not __import__("math").isnan(float(row["Volume"])) else 0,
                        interval_minutes=1,
                    )
                    bars.append(bar)
                except Exception:
                    continue
            if bars:
                result[sym] = tuple(bars)
        except Exception:
            continue
    return result



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
    row     = proj.row
    icon    = _STAGE_ICON.get(proj.stage_tag.value, "?")
    reason  = f" reason={proj.primary_invalid_reason}" if proj.primary_invalid_reason else ""
    support = "  " + " | ".join(proj.supporting_reasons) if proj.supporting_reasons else ""
    print(
        f"  #{rank:<2}  {row.symbol:<6}  "
        f"${_fmt(row.price)}  "
        f"chg={_fmt(row.change_from_prior_close_percent, '%')}  "
        f"rvol={_fmt(row.daily_relative_volume, 'x')}  "
        f"pullback={_fmt(row.pullback_from_high_percent, '%')}  "
        f"age={int(row.time_since_news_seconds // 60)}m  "
        f"score={proj.score:>3}  {icon} {proj.stage_tag.value}{reason}"
    )
    if support:
        print(f"         └─ {row.headline[:70]}{support}")


# ── Scan cycle ────────────────────────────────────────────────────────────────

async def run_once(
    session: aiohttp.ClientSession,
    polygon: PolygonSnapshotProvider,
    benzinga: BenzingaNewsProvider,
    finnhub_key: str,
    now: datetime,
) -> None:
    print(f"\n{'━'*80}")
    print(f"  Scan at {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'━'*80}")

    # 1. Fetch Benzinga news
    print("  [1/4] Fetching Benzinga news …", end=" ", flush=True)
    news_batch = await benzinga.fetch_recent_news(SEED_SYMBOLS, limit=NEWS_LIMIT)
    news_events = news_batch.records
    print(f"{len(news_events)} events")

    if not news_events:
        print("  No news — nothing to scan.")
        return

    # 2. Link news to symbols, cap universe
    news_by_symbol = latest_news_by_symbol(news_events)
    # Prefer symbols in our seed list (US equities); put seed symbols first
    seed_set = set(s.upper() for s in SEED_SYMBOLS)
    ordered = sorted(
        news_by_symbol.keys(),
        key=lambda s: (0 if s in seed_set else 1, s),
    )
    active_symbols = ordered[:MAX_SYMBOLS]
    disp = ", ".join(active_symbols[:12])
    more = f" … +{len(active_symbols)-12} more" if len(active_symbols) > 12 else ""
    print(f"  [2/4] Symbols with news ({len(active_symbols)}): {disp}{more}")

    # 3. Fetch Finnhub quotes + Polygon daily bars + yfinance intraday (concurrently)
    print(f"  [3/4] Fetching quotes, daily bars + intraday …", end=" ", flush=True)
    quotes_task = fetch_finnhub_quotes(session, active_symbols, finnhub_key, now)
    bars_task   = fetch_polygon_daily_bars(polygon, active_symbols, LOOKBACK_DAYS)
    snapshots, daily_bars = await asyncio.gather(quotes_task, bars_task)

    # yfinance is synchronous — run in executor so it doesn't block the event loop
    loop = asyncio.get_event_loop()
    intraday_by_sym = await loop.run_in_executor(
        None, fetch_intraday_bars_yf, active_symbols
    )
    total_intraday = sum(len(v) for v in intraday_by_sym.values())
    print(f"{len(snapshots)} quotes, {len(daily_bars)} daily bars, {total_intraday} intraday bars")

    # 4. Build candidate rows → run full scanner signal chain
    print("  [4/4] Running scanner signal chain …")
    projections: list[StrategyProjection] = []
    for symbol in active_symbols:
        linked_news = news_by_symbol.get(symbol)
        snapshot    = snapshots.get(symbol)
        if linked_news is None or snapshot is None:
            continue

        # metrics → CandidateRow
        metrics = build_market_metrics(
            snapshot,
            daily_bars=daily_bars,
            current_bar=None,
            historical_intraday_bars=(),
            lookback_days=LOOKBACK_DAYS,
        )
        row = build_candidate_row(snapshot, linked_news, metrics)
        if row is None:
            continue

        # context → validity → trigger → invalidation → projection
        intraday_bars = intraday_by_sym.get(symbol, ())
        context  = build_context_features(snapshot, intraday_bars=intraday_bars)
        validity = evaluate_setup_validity(row, linked_news, context)

        # Trigger: preferred=15s (not available from yfinance), fallback=60s (1m bars)
        trigger_selection = resolve_trigger_bars(
            preferred_bars=(),          # no 15s bars yet
            fallback_bars=intraday_bars,
        )
        trigger = evaluate_first_break_trigger(trigger_selection)

        # Invalidation gate (runs after validity check)
        invalidation = evaluate_invalidation(
            row, linked_news, context,
            setup_validity=validity,
        )

        proj = project_strategy_row(
            row,
            context_features=context,
            setup_validity=validity,
            trigger_evaluation=trigger,
            invalidation=invalidation,
        )
        projections.append(proj)

    if not projections:
        print("  No candidate rows built.")
        return

    # Sort: valid first, then score descending
    projections.sort(key=lambda p: (not p.is_valid, -p.score))

    valid   = [p for p in projections if p.is_valid]
    invalid = [p for p in projections if not p.is_valid]

    print(f"\n  {'─'*76}")
    print(f"  {len(valid)} valid setup(s)  |  {len(invalid)} invalid  |  {len(projections)} total")
    print(f"  {'─'*76}")

    if valid:
        print(f"  ✅ VALID SETUPS (scored, ranked):")
        for i, proj in enumerate(valid, 1):
            print_projection(i, proj)
        print()

    # Always show top invalid setups so you can see what's blocking them
    show_invalid = invalid[:10]
    if show_invalid:
        print(f"  ⚠️  TOP INVALID ({len(invalid)} total — top {len(show_invalid)} shown):")
        for i, proj in enumerate(show_invalid, 1):
            print_projection(i, proj)

    print(f"  {'─'*76}")


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    config = AppConfig.from_env()
    finnhub_key = os.environ.get("FINNHUB_API_KEY", "")

    if not finnhub_key:
        print("ERROR: FINNHUB_API_KEY not set. Run: export $(cat .env | xargs)")
        sys.exit(1)
    if not config.benzinga.api_key:
        print("ERROR: BENZINGA_API_KEY not set.")
        sys.exit(1)

    print("=" * 80)
    print("  Buy Signal — Live Scanner")
    print("=" * 80)
    print(f"  Quotes   : Finnhub (real-time)")
    print(f"  History  : Polygon (daily bars, RVOL)")
    print(f"  News     : Benzinga")
    print(f"  Poll     : every {POLL_INTERVAL_SEC}s  |  Min move: >= {MIN_CHANGE_PCT}%")
    print(f"  Universe : {len(SEED_SYMBOLS)} seed symbols, cap {MAX_SYMBOLS}/scan")
    print()

    async with aiohttp.ClientSession() as session:
        polygon  = PolygonSnapshotProvider(config.polygon,  fetch_json=make_polygon_fetcher(session))
        benzinga = BenzingaNewsProvider(config.benzinga, fetch_json=make_benzinga_fetcher(session))

        while True:
            now = datetime.now(UTC)
            try:
                await run_once(session, polygon, benzinga, finnhub_key, now)
            except Exception as exc:
                print(f"\n  [ERROR] {type(exc).__name__}: {exc}")
            print(f"\n  Next scan in {POLL_INTERVAL_SEC}s … (Ctrl-C to stop)")
            await asyncio.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    asyncio.run(main())
