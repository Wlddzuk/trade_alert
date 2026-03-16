from __future__ import annotations

from decimal import Decimal

from app.alerts.models import TradeProposal

from .models import PositionSize, RiskDefaults


def calculate_position_size(
    proposal: TradeProposal,
    *,
    account_equity: Decimal | float | int | str,
    defaults: RiskDefaults | None = None,
) -> PositionSize | None:
    risk_defaults = defaults or RiskDefaults()
    equity = Decimal(str(account_equity))
    if equity <= 0:
        raise ValueError("account_equity must be greater than zero")

    risk_budget = equity * risk_defaults.risk_per_trade_fraction
    risk_per_share = proposal.entry_price - proposal.stop_price
    if risk_per_share <= 0:
        raise ValueError("proposal stop must remain below entry for long trades")

    quantity = int(risk_budget / risk_per_share)
    if quantity <= 0:
        return None

    return PositionSize(
        quantity=quantity,
        risk_budget=risk_budget,
        risk_per_share=risk_per_share,
        estimated_notional=proposal.entry_price * Decimal(quantity),
    )
