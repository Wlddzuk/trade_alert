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
MAX_SYMBOLS       = 50    # raised from 40 — 3-layer discovery needs headroom
PEER_BUDGET       = 10    # max Finnhub /peers calls per cycle (rate-limit safe)
PEER_CACHE_TTL    = 86400 # 24 hours — peers rarely change
# ─────────────────────────────────────────────────────────────────────────────

# Seed symbols are used as a priority boost, NOT a filter.
# The scanner fetches ALL recent Benzinga news, then prioritizes
# seed symbols when capping to MAX_SYMBOLS.  Unknown tickers
# discovered via news still get scanned.
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


# ── Layer 2: Finnhub sector peer expansion (cached) ─────────────────────────

_peer_cache: dict[str, tuple[list[str], float]] = {}   # symbol → (peers, epoch)


async def finnhub_peers(
    session: aiohttp.ClientSession,
    symbol: str,
    api_key: str,
) -> list[str]:
    """Fetch peers for one symbol from Finnhub /stock/peers. Cached 24h."""
    now_ts = time.time()
    if symbol in _peer_cache:
        peers, cached_at = _peer_cache[symbol]
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
            _peer_cache[symbol] = (peers, now_ts)
            return peers
    except Exception:
        return []


async def expand_with_peers(
    session: aiohttp.ClientSession,
    news_symbols: list[str],
    api_key: str,
) -> list[str]:
    """
    Layer 2: for each news-mentioned symbol, discover sector peers.
    Only fetches uncached symbols, up to PEER_BUDGET per cycle.
    Returns NEW symbols not already in news_symbols.
    """
    uncached = [s for s in news_symbols if s not in _peer_cache][:PEER_BUDGET]
    if uncached:
        await asyncio.gather(*[finnhub_peers(session, s, api_key) for s in uncached])

    all_peers: set[str] = set()
    news_set = set(news_symbols)
    for sym in news_symbols:
        if sym in _peer_cache:
            peers, _ = _peer_cache[sym]
            all_peers.update(peers[:5])  # top 5 peers per symbol

    return sorted(all_peers - news_set)


# ── Layer 3: top market movers via yfinance screener ─────────────────────────

def fetch_top_movers_yf(min_change_pct: float = 3.0, max_results: int = 25) -> list[str]:
    """
    Layer 3: discover unknown small-cap movers spiking on volume.
    Uses yfinance custom screener: NASDAQ/NYSE, <2B mcap, >3% change, >50k vol.
    Returns list of symbols sorted by % change descending.
    """
    try:
        from yfinance import EquityQuery
        q = EquityQuery("and", [
            EquityQuery("gt", ["percentchange", min_change_pct]),
            EquityQuery("eq", ["region", "us"]),
            EquityQuery("lt", ["intradaymarketcap", 2_000_000_000]),
            EquityQuery("gte", ["intradayprice", 1]),
            EquityQuery("gt", ["dayvolume", 50_000]),
            EquityQuery("is-in", ["exchange", "NMS", "NYQ"]),
        ])
        result = yf.screen(q, sortField="percentchange", sortAsc=False, size=max_results)
        return [r["symbol"] for r in result.get("quotes", []) if "symbol" in r]
    except Exception:
        return []


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

    # Prefer the granular validity reason over the masked 'setup_invalid' from invalidation
    real_reason = proj.primary_invalid_reason
    if (
        real_reason == "setup_invalid"
        and proj.setup_validity.primary_invalid_reason is not None
    ):
        real_reason = proj.setup_validity.primary_invalid_reason.value

    reason  = f" reason={real_reason}" if real_reason else ""
    support = "  " + " | ".join(
        r for r in proj.supporting_reasons if r != f"invalid={proj.primary_invalid_reason}"
    ) if proj.supporting_reasons else ""
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
    else:
        print(f"         └─ {row.headline[:80]}")


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

    # ── LAYER 1: Benzinga news firehose (no ticker filter) ───────────────
    print("  [1/6] Benzinga news (all tickers) …", end=" ", flush=True)
    news_batch = await benzinga.fetch_recent_news(limit=NEWS_LIMIT)
    news_events = news_batch.records
    print(f"{len(news_events)} events")

    if not news_events:
        print("  No news — nothing to scan.")
        return

    news_by_symbol = latest_news_by_symbol(news_events)
    news_symbols = list(news_by_symbol.keys())
    print(f"         → {len(news_symbols)} tickers mentioned in news")

    # ── LAYER 2: Sector peer expansion via Finnhub ───────────────────────
    print(f"  [2/6] Peer expansion ({len(_peer_cache)} cached) …", end=" ", flush=True)
    peer_symbols = await expand_with_peers(session, news_symbols, finnhub_key)
    print(f"+{len(peer_symbols)} peers")

    # ── LAYER 3: Top small-cap movers via yfinance screener ──────────────
    print("  [3/6] Small-cap movers screener …", end=" ", flush=True)
    loop = asyncio.get_event_loop()
    mover_symbols = await loop.run_in_executor(None, fetch_top_movers_yf)
    # Filter out any already in news or peers
    existing = set(news_symbols) | set(peer_symbols)
    new_movers = [s for s in mover_symbols if s not in existing]
    print(f"{len(mover_symbols)} movers, {len(new_movers)} new")

    # ── Merge & prioritize universe ──────────────────────────────────────
    # Priority: news tickers first (seed boost), then peers, then movers
    seed_set = set(s.upper() for s in SEED_SYMBOLS)
    all_candidates = []
    sources: dict[str, str] = {}  # symbol → discovery source

    for s in news_symbols:
        all_candidates.append(s)
        sources[s] = "news"
    for s in peer_symbols:
        if s not in sources:
            all_candidates.append(s)
            sources[s] = "peer"
    for s in new_movers:
        if s not in sources:
            all_candidates.append(s)
            sources[s] = "mover"

    # Reserve slots so peers/movers don't get crowded out by news
    # Allocation: up to 35 news, up to 10 peers, up to 10 movers (= 55 max, capped to 50)
    news_list   = [s for s in all_candidates if sources[s] == "news"]
    peer_list   = [s for s in all_candidates if sources[s] == "peer"]
    mover_list  = [s for s in all_candidates if sources[s] == "mover"]
    active_symbols = news_list[:35] + peer_list[:10] + mover_list[:10]
    active_symbols = active_symbols[:MAX_SYMBOLS]

    n_news   = sum(1 for s in active_symbols if sources[s] == "news")
    n_peers  = sum(1 for s in active_symbols if sources[s] == "peer")
    n_movers = sum(1 for s in active_symbols if sources[s] == "mover")
    disp = ", ".join(active_symbols[:12])
    more = f" … +{len(active_symbols)-12} more" if len(active_symbols) > 12 else ""
    print(f"  [4/6] Universe: {len(active_symbols)} symbols "
          f"({n_news} news, {n_peers} peers, {n_movers} movers): {disp}{more}")

    # ── Fetch market data for full universe ──────────────────────────────
    print(f"  [5/6] Fetching quotes, daily bars + intraday …", end=" ", flush=True)
    quotes_task = fetch_finnhub_quotes(session, active_symbols, finnhub_key, now)
    bars_task   = fetch_polygon_daily_bars(polygon, active_symbols, LOOKBACK_DAYS)
    snapshots, daily_bars = await asyncio.gather(quotes_task, bars_task)

    # yfinance is synchronous — run in executor
    intraday_by_sym = await loop.run_in_executor(
        None, fetch_intraday_bars_yf, active_symbols
    )
    total_intraday = sum(len(v) for v in intraday_by_sym.values())
    print(f"{len(snapshots)} quotes, {len(daily_bars)} daily bars, {total_intraday} intraday bars")

    # ── Run scanner signal chain ─────────────────────────────────────────
    print("  [6/6] Running scanner signal chain …")
    projections: list[StrategyProjection] = []
    newsless_movers: list[tuple[str, str, MarketSnapshot]] = []  # (sym, source, snap)

    for symbol in active_symbols:
        snapshot = snapshots.get(symbol)
        if snapshot is None:
            continue

        linked_news = news_by_symbol.get(symbol)
        if linked_news is None:
            # Peer or mover with no news — track for display but skip signal chain
            newsless_movers.append((symbol, sources.get(symbol, "?"), snapshot))
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

    if not projections and not newsless_movers:
        print("  No candidate rows built.")
        return

    # Sort: valid first, then score descending
    projections.sort(key=lambda p: (not p.is_valid, -p.score))

    valid   = [p for p in projections if p.is_valid]
    invalid = [p for p in projections if not p.is_valid]

    print(f"\n  {'─'*76}")
    print(f"  {len(valid)} valid setup(s)  |  {len(invalid)} invalid  |  "
          f"{len(projections)} scored  |  {len(newsless_movers)} watchlist")
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

    # Show discovered peers/movers without news
    if newsless_movers:
        print(f"\n  👀 WATCHLIST — no news yet ({len(newsless_movers)} symbols via peer/mover discovery):")
        for sym, src, snap in newsless_movers[:15]:
            price = snap.last_price
            chg = ""
            if snap.previous_close:
                try:
                    pct = (float(price) - float(snap.previous_close)) / float(snap.previous_close) * 100
                    chg = f"  chg={pct:+.1f}%"
                except (ValueError, ZeroDivisionError):
                    pass
            tag = "🔗" if src == "peer" else "📈"
            print(f"    {tag} {sym:<6}  ${price}{chg}  [{src}]")

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
    print("  Buy Signal — Live Scanner (3-layer discovery)")
    print("=" * 80)
    print(f"  Layer 1  : Benzinga news firehose (all tickers)")
    print(f"  Layer 2  : Finnhub sector peer expansion (cached 24h)")
    print(f"  Layer 3  : yfinance small-cap movers screener")
    print(f"  Quotes   : Finnhub (real-time)")
    print(f"  History  : Polygon (daily bars, RVOL)")
    print(f"  Poll     : every {POLL_INTERVAL_SEC}s  |  Cap: {MAX_SYMBOLS}/scan")
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
