from __future__ import annotations

from decimal import Decimal

from app.alerts.models import TradeProposal

from .models import RiskDefaults, TradeGateDecision, TradeGateReason, TradeQualitySnapshot
from .sizing import calculate_position_size


def evaluate_trade_gates(
    proposal: TradeProposal | None,
    quality: TradeQualitySnapshot,
    *,
    account_equity: Decimal | float | int | str,
    defaults: RiskDefaults | None = None,
) -> TradeGateDecision:
    risk_defaults = defaults or RiskDefaults()

    if proposal is None:
        return TradeGateDecision(False, reason=TradeGateReason.MISSING_STOP)
    if quality.average_daily_volume is None or quality.average_daily_volume < risk_defaults.min_average_daily_volume:
        return TradeGateDecision(False, reason=TradeGateReason.INSUFFICIENT_LIQUIDITY)
    if quality.live_liquidity_thin:
        return TradeGateDecision(False, reason=TradeGateReason.INSUFFICIENT_LIQUIDITY)
    if quality.spread_percent is not None and quality.spread_percent > risk_defaults.max_spread_percent:
        return TradeGateDecision(False, reason=TradeGateReason.SPREAD_TOO_WIDE)

    position_size = calculate_position_size(
        proposal,
        account_equity=account_equity,
        defaults=risk_defaults,
    )
    if position_size is None:
        return TradeGateDecision(False, reason=TradeGateReason.STOP_DISTANCE_TOO_WIDE)
    return TradeGateDecision(True, position_size=position_size)
