from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from app.alerts.models import PreEntryAlert
from app.providers.models import ensure_utc


class AdjustmentSessionStage(StrEnum):
    AWAITING_STOP = "awaiting_stop"
    AWAITING_TARGET = "awaiting_target"
    AWAITING_CONFIRMATION = "awaiting_confirmation"


class AdjustmentSessionStatus(StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    CONFIRMED = "confirmed"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class AdjustmentSession:
    actor_id: str
    alert: PreEntryAlert
    stage: AdjustmentSessionStage
    started_at: datetime
    expires_at: datetime
    stop_price: Decimal
    target_price: Decimal
    stop_changed: bool = False
    target_changed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "started_at", ensure_utc(self.started_at, field_name="started_at"))
        object.__setattr__(self, "expires_at", ensure_utc(self.expires_at, field_name="expires_at"))
        cleaned_actor_id = self.actor_id.strip()
        if not cleaned_actor_id:
            raise ValueError("actor_id must not be empty")
        object.__setattr__(self, "actor_id", cleaned_actor_id)


@dataclass(frozen=True, slots=True)
class AdjustmentSessionResult:
    status: AdjustmentSessionStatus
    session: AdjustmentSession | None = None
    message: str | None = None


def _parse_level_input(raw_value: str, *, field_name: str) -> Decimal | None:
    cleaned = raw_value.strip().lower()
    if cleaned in {"keep", "same"}:
        return None
    try:
        level = Decimal(cleaned)
    except Exception as exc:  # pragma: no cover - Decimal error type varies
        raise ValueError(f"{field_name} must be a decimal price or 'keep'") from exc
    if level <= 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return level


class AdjustmentSessionStore:
    def __init__(self, *, timeout: timedelta = timedelta(minutes=5)) -> None:
        self.timeout = timeout
        self._sessions: dict[str, AdjustmentSession] = {}

    def start(
        self,
        *,
        actor_id: str,
        alert: PreEntryAlert,
        observed_at: datetime,
    ) -> AdjustmentSession:
        current_time = ensure_utc(observed_at, field_name="observed_at")
        session = AdjustmentSession(
            actor_id=actor_id,
            alert=alert,
            stage=AdjustmentSessionStage.AWAITING_STOP,
            started_at=current_time,
            expires_at=current_time + self.timeout,
            stop_price=alert.proposal.stop_price,
            target_price=alert.proposal.target_price,
        )
        self._sessions[actor_id] = session
        return session

    def current(self, actor_id: str) -> AdjustmentSession | None:
        return self._sessions.get(actor_id)

    def cancel(self, actor_id: str) -> AdjustmentSessionResult:
        session = self._sessions.pop(actor_id, None)
        return AdjustmentSessionResult(
            status=AdjustmentSessionStatus.CANCELLED,
            session=session,
            message="Adjustment cancelled. Current alert proposal remains unchanged.",
        )

    def handle_text(
        self,
        *,
        actor_id: str,
        text: str,
        observed_at: datetime,
    ) -> AdjustmentSessionResult:
        session = self._sessions.get(actor_id)
        if session is None:
            return AdjustmentSessionResult(
                status=AdjustmentSessionStatus.INVALID,
                message="No active adjustment session. Start from the latest actionable alert.",
            )

        current_time = ensure_utc(observed_at, field_name="observed_at")
        if current_time > session.expires_at:
            self._sessions.pop(actor_id, None)
            return AdjustmentSessionResult(
                status=AdjustmentSessionStatus.EXPIRED,
                session=session,
                message="Adjustment session expired. Start again from the latest actionable alert.",
            )

        cleaned_text = text.strip()
        lowered = cleaned_text.lower()
        if lowered == "cancel":
            self._sessions.pop(actor_id, None)
            return AdjustmentSessionResult(
                status=AdjustmentSessionStatus.CANCELLED,
                session=session,
                message="Adjustment cancelled. Current alert proposal remains unchanged.",
            )

        if session.stage is AdjustmentSessionStage.AWAITING_STOP:
            try:
                stop_price = _parse_level_input(cleaned_text, field_name="stop_price")
            except ValueError as exc:
                return AdjustmentSessionResult(
                    status=AdjustmentSessionStatus.INVALID,
                    session=session,
                    message=str(exc),
                )
            updated = AdjustmentSession(
                actor_id=session.actor_id,
                alert=session.alert,
                stage=AdjustmentSessionStage.AWAITING_TARGET,
                started_at=session.started_at,
                expires_at=session.expires_at,
                stop_price=session.stop_price if stop_price is None else stop_price,
                target_price=session.target_price,
                stop_changed=stop_price is not None and stop_price != session.alert.proposal.stop_price,
                target_changed=session.target_changed,
            )
            self._sessions[actor_id] = updated
            return AdjustmentSessionResult(
                status=AdjustmentSessionStatus.ACTIVE,
                session=updated,
            )

        if session.stage is AdjustmentSessionStage.AWAITING_TARGET:
            try:
                target_price = _parse_level_input(cleaned_text, field_name="target_price")
            except ValueError as exc:
                return AdjustmentSessionResult(
                    status=AdjustmentSessionStatus.INVALID,
                    session=session,
                    message=str(exc),
                )
            updated = AdjustmentSession(
                actor_id=session.actor_id,
                alert=session.alert,
                stage=AdjustmentSessionStage.AWAITING_CONFIRMATION,
                started_at=session.started_at,
                expires_at=session.expires_at,
                stop_price=session.stop_price,
                target_price=session.target_price if target_price is None else target_price,
                stop_changed=session.stop_changed,
                target_changed=target_price is not None and target_price != session.alert.proposal.target_price,
            )
            self._sessions[actor_id] = updated
            return AdjustmentSessionResult(
                status=AdjustmentSessionStatus.ACTIVE,
                session=updated,
            )

        if lowered not in {"confirm", "approve", "yes"}:
            return AdjustmentSessionResult(
                status=AdjustmentSessionStatus.INVALID,
                session=session,
                message="Reply 'confirm' to apply the adjusted levels or 'cancel' to abandon them.",
            )

        self._sessions.pop(actor_id, None)
        return AdjustmentSessionResult(
            status=AdjustmentSessionStatus.CONFIRMED,
            session=session,
        )
