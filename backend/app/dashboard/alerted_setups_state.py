"""Shared state for *alerted* setups — one entry per symbol we've fired a
"NEW SETUP" message for, tracked through its lifecycle (alerted → t1_hit →
t2_hit / stopped / invalidated / expired). Consumed by the dashboard so the
user can see at a glance which setups are live and what stage they're in.

Kept separate from `scanner_state` because scanner rows are the full scan
universe (50 symbols per tick) while alerted setups are the small set that
actually produced a Telegram alert.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


@dataclass
class AlertedSetup:
    """One live setup we've alerted on. Lifecycle state machine:
        alerted → t1_hit → t2_hit   (WIN path)
        alerted → stopped            (LOSS)
        alerted → t1_hit → stopped   (BREAKEVEN — stop moved to entry)
        alerted → invalidated        (LOSS — setup broke)
        alerted → expired            (BREAKEVEN — no follow-through)
    """

    symbol: str
    first_alerted_at: datetime
    trigger_price: Decimal
    entry_price: Decimal
    stop_price: Decimal
    target_1: Decimal
    target_2: Decimal
    trigger_bar_started_at: datetime

    # Entry-time snapshot — captured so we can record a full OutcomeRecord
    # when the setup reaches a terminal state, without having to re-fetch
    # scanner data that may have moved on by then.
    catalyst_tag: str = ""
    catalyst_quality: str | None = None
    sentiment_direction: str | None = None
    sentiment_confidence: float | None = None
    agent_review_status: str | None = None
    agent_review_decision: str | None = None
    agent_review_error: str | None = None
    score_at_entry: int = 0
    daily_rvol: Decimal | None = None
    short_term_rvol: Decimal | None = None
    change_percent: Decimal | None = None
    gap_percent: Decimal | None = None

    # Lifecycle
    stage: str = "alerted"  # alerted | t1_hit | t2_hit | stopped | invalidated | expired
    peak_price: Decimal | None = None
    closed_at: datetime | None = None
    invalidation_reason: str | None = None

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None

    @property
    def is_terminal_stage(self) -> bool:
        return self.stage in ("t2_hit", "stopped", "invalidated", "expired")


def _dec_to_str(v: Decimal | None) -> str | None:
    return str(v) if v is not None else None


def _setup_to_dict(s: AlertedSetup) -> dict[str, Any]:
    return {
        "symbol": s.symbol,
        "stage": s.stage,
        "first_alerted_at": s.first_alerted_at.isoformat(),
        "trigger_bar_started_at": s.trigger_bar_started_at.isoformat(),
        "closed_at": s.closed_at.isoformat() if s.closed_at else None,
        "trigger_price": float(s.trigger_price),
        "entry_price": float(s.entry_price),
        "stop_price": float(s.stop_price),
        "target_1": float(s.target_1),
        "target_2": float(s.target_2),
        "peak_price": float(s.peak_price) if s.peak_price is not None else None,
        "catalyst_tag": s.catalyst_tag,
        "catalyst_quality": s.catalyst_quality,
        "sentiment_direction": s.sentiment_direction,
        "agent_review_status": s.agent_review_status,
        "agent_review_decision": s.agent_review_decision,
        "agent_review_error": s.agent_review_error,
        "score_at_entry": s.score_at_entry,
        "daily_rvol": float(s.daily_rvol) if s.daily_rvol is not None else None,
        "change_percent": float(s.change_percent) if s.change_percent is not None else None,
        "gap_percent": float(s.gap_percent) if s.gap_percent is not None else None,
        "invalidation_reason": s.invalidation_reason,
        "is_closed": s.is_closed,
    }


class AlertedSetupsState:
    """Thread-safe(ish) snapshot of active + recently-closed setups,
    consumed by the `/api/alerted-setups` endpoint."""

    def __init__(self) -> None:
        self._setups: list[AlertedSetup] = []
        self._last_updated_at: datetime | None = None

    def replace(self, setups: list[AlertedSetup]) -> None:
        self._setups = list(setups)
        self._last_updated_at = datetime.now(UTC)

    def snapshot(self) -> list[AlertedSetup]:
        return list(self._setups)

    def to_json(self) -> dict[str, Any]:
        # Order: active first (newest first), then recently-closed (newest first)
        active = [s for s in self._setups if not s.is_closed]
        closed = [s for s in self._setups if s.is_closed]
        active.sort(key=lambda s: s.first_alerted_at, reverse=True)
        closed.sort(key=lambda s: s.closed_at or s.first_alerted_at, reverse=True)

        return {
            "last_updated_at": self._last_updated_at.isoformat() if self._last_updated_at else None,
            "active_count": len(active),
            "closed_count": len(closed),
            "setups": [_setup_to_dict(s) for s in (active + closed)],
        }

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_json()).encode("utf-8")


# Module-level singleton
_state = AlertedSetupsState()


def get_alerted_setups_state() -> AlertedSetupsState:
    return _state
