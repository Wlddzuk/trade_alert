"""Persistent outcome store — records trade results for the learning layer.

Stores OutcomeRecords as JSON in a local file so the adaptive scorer can
learn from historical patterns across app restarts.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from .models import OutcomeRecord, TradeOutcome

logger = logging.getLogger(__name__)

_DEFAULT_STORE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "outcomes.json"


def _decimal_default(obj: object) -> object:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _record_to_dict(record: OutcomeRecord) -> dict:
    return {
        "trade_id": record.trade_id,
        "symbol": record.symbol,
        "entered_at": record.entered_at.isoformat(),
        "closed_at": record.closed_at.isoformat() if record.closed_at else None,
        "catalyst_tag": record.catalyst_tag,
        "catalyst_quality": record.catalyst_quality,
        "sentiment_direction": record.sentiment_direction,
        "sentiment_confidence": record.sentiment_confidence,
        "entry_price": str(record.entry_price),
        "stop_price": str(record.stop_price) if record.stop_price else None,
        "target_price": str(record.target_price) if record.target_price else None,
        "score_at_entry": record.score_at_entry,
        "daily_rvol": str(record.daily_rvol) if record.daily_rvol else None,
        "short_term_rvol": str(record.short_term_rvol) if record.short_term_rvol else None,
        "change_percent": str(record.change_percent) if record.change_percent else None,
        "gap_percent": str(record.gap_percent) if record.gap_percent else None,
        "hour_of_day": record.hour_of_day,
        "exit_price": str(record.exit_price) if record.exit_price else None,
        "realized_pnl": str(record.realized_pnl) if record.realized_pnl else None,
        "outcome": record.outcome.value,
    }


def _dict_to_record(data: dict) -> OutcomeRecord:
    return OutcomeRecord(
        trade_id=data["trade_id"],
        symbol=data["symbol"],
        entered_at=datetime.fromisoformat(data["entered_at"]),
        closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
        catalyst_tag=data["catalyst_tag"],
        catalyst_quality=data.get("catalyst_quality"),
        sentiment_direction=data.get("sentiment_direction"),
        sentiment_confidence=data.get("sentiment_confidence"),
        entry_price=Decimal(data["entry_price"]),
        stop_price=Decimal(data["stop_price"]) if data.get("stop_price") else None,
        target_price=Decimal(data["target_price"]) if data.get("target_price") else None,
        score_at_entry=int(data["score_at_entry"]),
        daily_rvol=Decimal(data["daily_rvol"]) if data.get("daily_rvol") else None,
        short_term_rvol=Decimal(data["short_term_rvol"]) if data.get("short_term_rvol") else None,
        change_percent=Decimal(data["change_percent"]) if data.get("change_percent") else None,
        gap_percent=Decimal(data["gap_percent"]) if data.get("gap_percent") else None,
        hour_of_day=int(data["hour_of_day"]),
        exit_price=Decimal(data["exit_price"]) if data.get("exit_price") else None,
        realized_pnl=Decimal(data["realized_pnl"]) if data.get("realized_pnl") else None,
        outcome=TradeOutcome(data.get("outcome", "open")),
    )


class OutcomeStore:
    """JSON-file-backed store for trade outcome records."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else _DEFAULT_STORE_PATH
        self._records: list[OutcomeRecord] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._records = [_dict_to_record(d) for d in raw]
            logger.info("Loaded %d outcome records from %s", len(self._records), self.path)
        except Exception:
            logger.exception("Failed to load outcome store from %s", self.path)
            self._records = []

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [_record_to_dict(r) for r in self._records]
        self.path.write_text(
            json.dumps(payload, indent=2, default=_decimal_default),
            encoding="utf-8",
        )

    def record_outcome(self, record: OutcomeRecord) -> None:
        """Add or update an outcome record and persist to disk."""
        self._ensure_loaded()
        # Update existing record if trade_id matches
        for i, existing in enumerate(self._records):
            if existing.trade_id == record.trade_id:
                self._records[i] = record
                self._persist()
                logger.info("Updated outcome for trade %s: %s", record.trade_id, record.outcome.value)
                return
        self._records.append(record)
        self._persist()
        logger.info("Recorded outcome for trade %s: %s", record.trade_id, record.outcome.value)

    def get_closed_records(self) -> list[OutcomeRecord]:
        """Return all completed trade records (not open)."""
        self._ensure_loaded()
        return [r for r in self._records if r.outcome != TradeOutcome.OPEN]

    def get_records_by_catalyst(self, catalyst_tag: str) -> list[OutcomeRecord]:
        """Return closed records filtered by catalyst type."""
        return [r for r in self.get_closed_records() if r.catalyst_tag == catalyst_tag]

    def get_records_by_hour(self, hour: int) -> list[OutcomeRecord]:
        """Return closed records filtered by entry hour (UTC)."""
        return [r for r in self.get_closed_records() if r.hour_of_day == hour]

    def get_records_with_sentiment(self) -> list[OutcomeRecord]:
        """Return closed records that had LLM sentiment analysis."""
        return [r for r in self.get_closed_records() if r.sentiment_direction is not None]

    def all_records(self) -> list[OutcomeRecord]:
        """Return all records including open trades."""
        self._ensure_loaded()
        return list(self._records)

    @property
    def total_closed(self) -> int:
        return len(self.get_closed_records())

    @property
    def win_rate(self) -> float | None:
        closed = self.get_closed_records()
        if not closed:
            return None
        wins = sum(1 for r in closed if r.outcome == TradeOutcome.WIN)
        return wins / len(closed)
