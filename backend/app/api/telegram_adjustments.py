from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.alerts.adjustment_sessions import (
    AdjustmentSessionResult,
    AdjustmentSessionStatus,
    AdjustmentSessionStore,
)
from app.alerts.action_resolution import (
    ParsedTelegramCallback,
    ResolutionStatus,
    TelegramActionRegistry,
    TelegramCallbackAction,
)
from app.alerts.models import PreEntryAlert
from app.alerts.telegram_renderer import (
    render_adjustment_confirmation,
    render_adjustment_stop_prompt,
    render_adjustment_target_prompt,
)


class TelegramAdjustmentStatus(StrEnum):
    NEEDS_INPUT = "needs_input"
    ACCEPTED = "accepted"
    STALE = "stale"
    INVALID = "invalid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class TelegramAdjustmentResult:
    status: TelegramAdjustmentStatus
    response_text: str
    alert: PreEntryAlert | None = None
    stop_changed: bool = False
    target_changed: bool = False
    stop_price: str | None = None
    target_price: str | None = None


class TelegramAdjustmentCoordinator:
    def __init__(
        self,
        *,
        registry: TelegramActionRegistry,
        sessions: AdjustmentSessionStore | None = None,
    ) -> None:
        self.registry = registry
        self.sessions = sessions or AdjustmentSessionStore()

    def start_entry_adjustment(
        self,
        *,
        actor_id: str,
        alert: PreEntryAlert,
        observed_at: datetime | None = None,
    ) -> TelegramAdjustmentResult:
        current_time = datetime.now(tz=UTC) if observed_at is None else observed_at.astimezone(UTC)
        session = self.sessions.start(actor_id=actor_id, alert=alert, observed_at=current_time)
        return TelegramAdjustmentResult(
            status=TelegramAdjustmentStatus.NEEDS_INPUT,
            response_text=render_adjustment_stop_prompt(session.alert).text,
            alert=alert,
        )

    def handle_message(
        self,
        *,
        actor_id: str,
        text: str,
        observed_at: datetime | None = None,
    ) -> TelegramAdjustmentResult:
        current_time = datetime.now(tz=UTC) if observed_at is None else observed_at.astimezone(UTC)
        result = self.sessions.handle_text(actor_id=actor_id, text=text, observed_at=current_time)
        return self._coerce_result(result)

    def _coerce_result(self, result: AdjustmentSessionResult) -> TelegramAdjustmentResult:
        session = result.session
        if result.status is AdjustmentSessionStatus.INVALID:
            return TelegramAdjustmentResult(
                status=TelegramAdjustmentStatus.INVALID,
                response_text=result.message or "Adjustment input was invalid.",
                alert=session.alert if session is not None else None,
            )
        if result.status is AdjustmentSessionStatus.CANCELLED:
            return TelegramAdjustmentResult(
                status=TelegramAdjustmentStatus.CANCELLED,
                response_text=result.message or "Adjustment cancelled.",
                alert=session.alert if session is not None else None,
            )
        if result.status is AdjustmentSessionStatus.EXPIRED:
            return TelegramAdjustmentResult(
                status=TelegramAdjustmentStatus.EXPIRED,
                response_text=result.message or "Adjustment session expired.",
                alert=session.alert if session is not None else None,
            )
        if result.status is AdjustmentSessionStatus.CONFIRMED:
            assert session is not None
            resolved = self.registry.resolve(
                ParsedTelegramCallback(
                    callback_query_id=f"adjust-confirm:{session.alert.alert_id}",
                    action=TelegramCallbackAction.ADJUST,
                    target_id=session.alert.alert_id,
                )
            )
            if resolved.status is not ResolutionStatus.READY:
                return TelegramAdjustmentResult(
                    status=TelegramAdjustmentStatus.STALE,
                    response_text=resolved.message,
                    alert=resolved.alert,
                )
            return TelegramAdjustmentResult(
                status=TelegramAdjustmentStatus.ACCEPTED,
                response_text=(
                    f"Adjusted entry confirmed for {session.alert.symbol}. "
                    f"Current alert proposal: entry {session.alert.proposal.entry_price.normalize():f}, "
                    f"stop {session.stop_price.normalize():f}, target {session.target_price.normalize():f}."
                ),
                alert=session.alert,
                stop_changed=session.stop_changed,
                target_changed=session.target_changed,
                stop_price=format(session.stop_price.normalize(), "f"),
                target_price=format(session.target_price.normalize(), "f"),
            )
        assert session is not None
        if session.stage.value == "awaiting_target":
            prompt = render_adjustment_target_prompt(
                session.alert,
                stop_price=session.stop_price,
            ).text
        else:
            prompt = render_adjustment_confirmation(
                session.alert,
                stop_price=session.stop_price,
                target_price=session.target_price,
            ).text
        return TelegramAdjustmentResult(
            status=TelegramAdjustmentStatus.NEEDS_INPUT,
            response_text=prompt,
            alert=session.alert,
        )
