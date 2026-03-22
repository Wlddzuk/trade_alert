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

from app.config import AppConfig
from app.providers.benzinga_adapter import BenzingaNewsProvider
from app.providers.models import (
    DailyBar,
    MarketSnapshot,
    ProviderCapability,
    ProviderHealthSnapshot,
    ProviderHealthState,
    ProviderBatch,
)
from app.providers.polygon_adapter import PolygonSnapshotProvider
from app.scanner.metrics import build_market_metrics
from app.scanner.news_linking import latest_news_by_symbol
from app.scanner.row_builder import build_candidate_row

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


# ── Output formatting ─────────────────────────────────────────────────────────

def _fmt(value, suffix="", d=2):
    if value is None:
        return "n/a"
    return f"{float(value):.{d}f}{suffix}"


def print_row(rank: int, row) -> None:
    print(
        f"  #{rank:<2}  {row.symbol:<6}  "
        f"${_fmt(row.price)}  "
        f"chg={_fmt(row.change_from_prior_close_percent, '%')}  "
        f"daily_rvol={_fmt(row.daily_relative_volume, 'x')}  "
        f"pullback={_fmt(row.pullback_from_high_percent, '%')}  "
        f"news_age={int(row.time_since_news_seconds // 60)}m  "
        f"[{row.catalyst_tag.value}]  {row.headline[:65]}"
    )


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

    # 3. Fetch Finnhub live quotes + Polygon daily bars concurrently
    print(f"  [3/4] Fetching Finnhub quotes + Polygon daily bars …", end=" ", flush=True)
    quotes_task = fetch_finnhub_quotes(session, active_symbols, finnhub_key, now)
    bars_task   = fetch_polygon_daily_bars(polygon, active_symbols, LOOKBACK_DAYS)
    snapshots, daily_bars = await asyncio.gather(quotes_task, bars_task)
    print(f"{len(snapshots)} quotes, {len(daily_bars)} bars")

    # 4. Compute metrics and build candidate rows
    print("  [4/4] Computing metrics …")
    rows = []
    for symbol in active_symbols:
        linked_news = news_by_symbol.get(symbol)
        snapshot    = snapshots.get(symbol)
        if linked_news is None or snapshot is None:
            continue
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
        rows.append(row)

    # Sort by change desc
    rows.sort(key=lambda r: float(r.change_from_prior_close_percent or 0), reverse=True)

    # Split: movers vs all
    movers = [r for r in rows if r.change_from_prior_close_percent is not None
              and float(r.change_from_prior_close_percent) >= MIN_CHANGE_PCT]

    if not movers:
        print(f"\n  No candidates >= {MIN_CHANGE_PCT}% move filter.")
        if rows:
            print(f"  All {len(rows)} symbols with news data (sorted by chg%):")
            print(f"  {'─'*76}")
            for i, r in enumerate(rows[:15], 1):
                print_row(i, r)
            print(f"  {'─'*76}")
        return

    print(f"\n  {'─'*76}")
    print(f"  {'#':<4}  {'SYM':<6}  {'PRICE':>8}  {'CHG%':>7}  {'RVOL':>8}  {'PULL%':>7}  {'AGE':>6}  TYPE  HEADLINE")
    print(f"  {'─'*76}")
    for i, row in enumerate(movers, 1):
        print_row(i, row)
    print(f"  {'─'*76}")
    print(f"  {len(movers)} candidate(s) surfaced  |  {len(rows)} total with data")


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
