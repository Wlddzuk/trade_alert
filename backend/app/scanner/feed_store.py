from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .models import CandidateRow


@dataclass(frozen=True, slots=True)
class CandidateFeedConfig:
    inactivity_timeout_seconds: float = 900.0

    def __post_init__(self) -> None:
        if self.inactivity_timeout_seconds <= 0:
            raise ValueError("inactivity_timeout_seconds must be greater than zero")


class CandidateFeedStore:
    """Maintains the current symbol-keyed candidate feed state."""

    def __init__(self, config: CandidateFeedConfig | None = None) -> None:
        self._config = config or CandidateFeedConfig()
        self._rows: dict[str, CandidateRow] = {}

    @property
    def config(self) -> CandidateFeedConfig:
        return self._config

    def upsert(self, row: CandidateRow) -> None:
        self._rows[row.symbol] = row

    def expire_inactive(self, observed_at: datetime) -> tuple[str, ...]:
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")

        cutoff = observed_at.astimezone(UTC)
        expired = tuple(
            symbol
            for symbol, row in self._rows.items()
            if (cutoff - row.observed_at).total_seconds() > self._config.inactivity_timeout_seconds
        )
        for symbol in expired:
            self._rows.pop(symbol, None)
        return expired

    def rows(self) -> tuple[CandidateRow, ...]:
        return tuple(self._rows.values())
