from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Iterable

from app.ops.health_models import SystemTrustSnapshot

from .feed_store import CandidateFeedStore
from .models import CandidateRow

if TYPE_CHECKING:
    from .strategy_projection import StrategyProjection


@dataclass(frozen=True, slots=True)
class CandidateFeedSnapshot:
    observed_at: datetime
    actionable: bool
    rows: tuple[CandidateRow, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))
        object.__setattr__(self, "rows", tuple(self.rows))


class CandidateFeedService:
    def __init__(self, store: CandidateFeedStore | None = None) -> None:
        self._store = store or CandidateFeedStore()

    @property
    def store(self) -> CandidateFeedStore:
        return self._store

    def refresh(
        self,
        rows: Iterable[CandidateRow],
        *,
        trust_snapshot: SystemTrustSnapshot,
        observed_at: datetime | None = None,
    ) -> CandidateFeedSnapshot:
        snapshot_time = trust_snapshot.observed_at if observed_at is None else self._ensure_aware(observed_at)
        self._store.expire_inactive(snapshot_time)

        if trust_snapshot.actionable:
            for row in rows:
                self._store.upsert(row)

        return CandidateFeedSnapshot(
            observed_at=snapshot_time,
            actionable=trust_snapshot.actionable,
            rows=self._ordered_rows(),
        )

    def _ordered_rows(self) -> tuple[CandidateRow, ...]:
        return tuple(
            sorted(
                self._store.rows(),
                key=lambda row: (
                    row.latest_news_at,
                    row.change_from_prior_close_percent or Decimal("-1"),
                ),
                reverse=True,
            )
        )

    def order_strategy_rows(
        self,
        rows: Iterable["StrategyProjection"],
    ) -> tuple["StrategyProjection", ...]:
        return tuple(
            sorted(
                rows,
                key=lambda projection: (
                    projection.is_valid,
                    projection.score,
                    projection.row.latest_news_at,
                    projection.row.change_from_prior_close_percent or Decimal("-1"),
                ),
                reverse=True,
            )
        )

    def _ensure_aware(self, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return value.astimezone(UTC)
