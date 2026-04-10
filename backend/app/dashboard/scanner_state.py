"""Shared in-memory state for live scanner data, consumed by the dashboard API."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class ScannerRow:
    """Flattened row for dashboard display — one per symbol per scan tick."""

    symbol: str
    price: float | None
    change_percent: float | None
    gap_percent: float | None
    volume: int
    avg_daily_volume: float | None
    daily_rvol: float | None
    short_term_rvol: float | None
    score: int
    stage: str  # "building", "trigger_ready", "invalid", "watching"
    primary_invalid_reason: str | None
    headline: str
    catalyst_tag: str
    catalyst_age_seconds: float | None
    vwap: float | None
    ema_9: float | None
    ema_20: float | None
    pullback_retracement_pct: float | None
    sentiment_direction: str | None  # "bullish", "bearish", "neutral"
    observed_at: str  # ISO timestamp


def _to_float(val: Decimal | float | int | None) -> float | None:
    if val is None:
        return None
    return float(val)


class ScannerState:
    """Thread-safe(ish) singleton holding the latest scanner snapshot."""

    def __init__(self) -> None:
        self._rows: list[ScannerRow] = []
        self._last_scan_at: datetime | None = None
        self._scan_duration: float = 0.0
        self._total_symbols: int = 0

    def update(
        self,
        rows: list[ScannerRow],
        *,
        scan_duration: float = 0.0,
        total_symbols: int = 0,
    ) -> None:
        self._rows = rows
        self._last_scan_at = datetime.now(UTC)
        self._scan_duration = scan_duration
        self._total_symbols = total_symbols

    def to_json(self) -> dict[str, Any]:
        return {
            "last_scan_at": self._last_scan_at.isoformat() if self._last_scan_at else None,
            "scan_duration_seconds": round(self._scan_duration, 2),
            "total_symbols_scanned": self._total_symbols,
            "rows": [
                {
                    "symbol": r.symbol,
                    "price": r.price,
                    "change_percent": r.change_percent,
                    "gap_percent": r.gap_percent,
                    "volume": r.volume,
                    "avg_daily_volume": r.avg_daily_volume,
                    "daily_rvol": r.daily_rvol,
                    "short_term_rvol": r.short_term_rvol,
                    "score": r.score,
                    "stage": r.stage,
                    "primary_invalid_reason": r.primary_invalid_reason,
                    "headline": r.headline,
                    "catalyst_tag": r.catalyst_tag,
                    "catalyst_age_seconds": r.catalyst_age_seconds,
                    "vwap": r.vwap,
                    "ema_9": r.ema_9,
                    "ema_20": r.ema_20,
                    "pullback_retracement_pct": r.pullback_retracement_pct,
                    "sentiment_direction": r.sentiment_direction,
                    "observed_at": r.observed_at,
                }
                for r in self._rows
            ],
        }

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_json()).encode("utf-8")


# Module-level singleton
_scanner_state = ScannerState()


def get_scanner_state() -> ScannerState:
    return _scanner_state
