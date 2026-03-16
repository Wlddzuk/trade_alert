from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

from app.providers.models import ensure_utc

from .models import RiskDefaults, SessionBlockReason, SessionGuardDecision, SessionState


def evaluate_session_guards(
    observed_at,
    session_state: SessionState,
    *,
    defaults: RiskDefaults | None = None,
) -> SessionGuardDecision:
    risk_defaults = defaults or RiskDefaults()
    observed_at = ensure_utc(observed_at, field_name="observed_at")

    daily_loss_limit = session_state.account_equity * risk_defaults.max_daily_loss_fraction
    if session_state.realized_pnl_today <= -daily_loss_limit:
        return SessionGuardDecision(False, reason=SessionBlockReason.MAX_DAILY_LOSS_REACHED)

    if session_state.open_positions >= risk_defaults.max_open_positions:
        return SessionGuardDecision(False, reason=SessionBlockReason.MAX_OPEN_POSITIONS)

    local_now = observed_at.astimezone(ZoneInfo(risk_defaults.trading_timezone))
    cutoff = local_now.replace(
        hour=risk_defaults.entry_cutoff_hour,
        minute=risk_defaults.entry_cutoff_minute,
        second=0,
        microsecond=0,
    )
    if local_now >= cutoff:
        return SessionGuardDecision(False, reason=SessionBlockReason.ENTRY_CUTOFF_REACHED)

    if session_state.last_loss_at is not None and session_state.consecutive_losses > 0:
        cooldown_seconds = (
            risk_defaults.cooldown_after_consecutive_losses_seconds
            if session_state.consecutive_losses >= 2
            else risk_defaults.cooldown_after_loss_seconds
        )
        blocked_until = session_state.last_loss_at + timedelta(seconds=cooldown_seconds)
        if observed_at < blocked_until:
            return SessionGuardDecision(
                False,
                reason=SessionBlockReason.COOLDOWN_ACTIVE,
                blocked_until=blocked_until,
            )

    return SessionGuardDecision(True)
