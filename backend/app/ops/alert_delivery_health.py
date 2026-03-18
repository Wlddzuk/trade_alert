from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from .monitoring_models import AlertDeliverySnapshot


@dataclass(frozen=True, slots=True)
class AlertDeliveryFailure:
    observed_at: datetime
    reason: str
    channel: str = "telegram"
    consecutive_failures: int = 1
    last_success_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))
        if self.last_success_at is not None:
            if self.last_success_at.tzinfo is None or self.last_success_at.utcoffset() is None:
                raise ValueError("last_success_at must be timezone-aware")
            object.__setattr__(self, "last_success_at", self.last_success_at.astimezone(UTC))
        if self.consecutive_failures <= 0:
            raise ValueError("consecutive_failures must be greater than zero")


@dataclass(frozen=True, slots=True)
class AlertFailureLog:
    recent_failures: tuple[AlertDeliveryFailure, ...]


class AlertDeliveryResult(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class AlertDeliveryAttempt:
    occurred_at: datetime
    symbol: str
    alert_id: str
    result: AlertDeliveryResult
    reason: str

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        object.__setattr__(self, "occurred_at", self.occurred_at.astimezone(UTC))
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "alert_id", self.alert_id.strip())
        object.__setattr__(self, "reason", self.reason.strip())


@dataclass(frozen=True, slots=True)
class AlertDeliveryHealthSnapshot:
    consecutive_failures: int
    summary: str
    last_attempt_at: datetime | None
    last_success_at: datetime | None


@dataclass(frozen=True, slots=True)
class AlertDeliveryHealthReport:
    snapshot: AlertDeliveryHealthSnapshot
    recent_failures: tuple[AlertDeliveryFailure, ...]


def build_alert_failure_log(
    failures: tuple[AlertDeliveryFailure, ...],
    *,
    limit: int = 10,
) -> AlertFailureLog:
    ordered = sorted(failures, key=lambda failure: failure.observed_at, reverse=True)
    return AlertFailureLog(recent_failures=tuple(ordered[:limit]))


def build_alert_delivery_snapshot(
    attempts: tuple[AlertDeliveryAttempt, ...],
    *,
    observed_at: datetime,
) -> AlertDeliverySnapshot:
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")

    ordered = tuple(sorted(attempts, key=lambda attempt: attempt.occurred_at, reverse=True))
    consecutive_failures = 0
    last_success_at = None
    last_failure_reason = None

    for attempt in ordered:
        if attempt.result is AlertDeliveryResult.FAILURE:
            consecutive_failures += 1
            if last_failure_reason is None:
                last_failure_reason = attempt.reason
        else:
            last_success_at = attempt.occurred_at
            break

    if last_success_at is None:
        last_success_at = next(
            (attempt.occurred_at for attempt in ordered if attempt.result is AlertDeliveryResult.SUCCESS),
            None,
        )

    return AlertDeliverySnapshot(
        observed_at=observed_at,
        last_attempt_at=ordered[0].occurred_at if ordered else None,
        last_success_at=last_success_at,
        consecutive_failures=consecutive_failures,
        last_failure_reason=last_failure_reason,
    )


class AlertDeliveryHealthService:
    def build_report(
        self,
        attempts: tuple[AlertDeliveryAttempt, ...],
        *,
        observed_at: datetime,
        failure_limit: int = 10,
    ) -> AlertDeliveryHealthReport:
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        ordered = tuple(sorted(attempts, key=lambda attempt: attempt.occurred_at, reverse=True))
        failures = self._recent_failures(ordered, limit=failure_limit)
        snapshot = build_alert_delivery_snapshot(ordered, observed_at=observed_at)
        if snapshot.consecutive_failures >= 3:
            summary = "Alert delivery failing repeatedly."
        elif snapshot.consecutive_failures > 0:
            summary = "Alert delivery failures detected."
        elif failures:
            summary = "Alert delivery recovered after recent failures."
        else:
            summary = "Alert delivery healthy."

        return AlertDeliveryHealthReport(
            snapshot=AlertDeliveryHealthSnapshot(
                consecutive_failures=snapshot.consecutive_failures,
                summary=summary,
                last_attempt_at=snapshot.last_attempt_at,
                last_success_at=snapshot.last_success_at,
            ),
            recent_failures=failures,
        )

    def _recent_failures(
        self,
        attempts: tuple[AlertDeliveryAttempt, ...],
        *,
        limit: int,
    ) -> tuple[AlertDeliveryFailure, ...]:
        failures: list[AlertDeliveryFailure] = []
        consecutive_failures = 0
        last_success_at = None

        for attempt in reversed(attempts):
            if attempt.result is AlertDeliveryResult.SUCCESS:
                consecutive_failures = 0
                last_success_at = attempt.occurred_at
                continue

            consecutive_failures += 1
            failures.append(
                AlertDeliveryFailure(
                    observed_at=attempt.occurred_at,
                    reason=attempt.reason,
                    consecutive_failures=consecutive_failures,
                    last_success_at=last_success_at,
                )
            )

        failures.sort(key=lambda failure: failure.observed_at, reverse=True)
        return tuple(failures[:limit])
