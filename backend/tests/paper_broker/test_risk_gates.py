from __future__ import annotations

from decimal import Decimal

from app.alerts.approval_workflow import approve_with_adjustments, approve_with_defaults
from app.paper.broker import PaperBroker
from app.risk.models import RiskDefaults, TradeGateReason, TradeQualitySnapshot
from app.risk.trade_gates import evaluate_trade_gates

from .test_entry_handling import _actionable_alert


def test_trade_gates_size_from_the_approved_entry_and_stop() -> None:
    decision = approve_with_adjustments(
        _actionable_alert(),
        stop_price="12.05",
        target_price="13.90",
    )

    gate = evaluate_trade_gates(
        decision.proposal,
        TradeQualitySnapshot(
            average_daily_volume="900000",
            spread_percent="0.20",
        ),
        account_equity="25000",
    )

    assert gate.passed is True
    assert gate.position_size.risk_per_share == Decimal("0.40")
    assert gate.position_size.quantity == 625


def test_trade_gates_reject_missing_stop_proposal() -> None:
    gate = evaluate_trade_gates(
        None,
        TradeQualitySnapshot(
            average_daily_volume="900000",
            spread_percent="0.20",
        ),
        account_equity="25000",
    )

    assert gate.passed is False
    assert gate.reason is TradeGateReason.MISSING_STOP


def test_trade_gates_reject_wide_spread() -> None:
    decision = approve_with_defaults(_actionable_alert())

    gate = evaluate_trade_gates(
        decision.proposal,
        TradeQualitySnapshot(
            average_daily_volume="900000",
            spread_percent="0.90",
        ),
        account_equity="25000",
    )

    assert gate.passed is False
    assert gate.reason is TradeGateReason.SPREAD_TOO_WIDE


def test_trade_gates_reject_thin_liquidity() -> None:
    decision = approve_with_defaults(_actionable_alert())

    gate = evaluate_trade_gates(
        decision.proposal,
        TradeQualitySnapshot(
            average_daily_volume="300000",
            spread_percent="0.20",
        ),
        account_equity="25000",
    )

    assert gate.passed is False
    assert gate.reason is TradeGateReason.INSUFFICIENT_LIQUIDITY


def test_trade_gates_reject_when_stop_distance_breaks_fixed_risk_model() -> None:
    decision = approve_with_adjustments(
        _actionable_alert(),
        stop_price="0.50",
        target_price="13.90",
    )

    gate = evaluate_trade_gates(
        decision.proposal,
        TradeQualitySnapshot(
            average_daily_volume="900000",
            spread_percent="0.20",
        ),
        account_equity="100",
    )

    assert gate.passed is False
    assert gate.reason is TradeGateReason.STOP_DISTANCE_TOO_WIDE


def test_broker_can_reuse_gate_sizing_for_final_entry() -> None:
    broker = PaperBroker()
    decision = approve_with_defaults(_actionable_alert())
    gate = evaluate_trade_gates(
        decision.proposal,
        TradeQualitySnapshot(
            average_daily_volume="900000",
            spread_percent="0.20",
        ),
        account_equity="25000",
    )

    trade = broker.open_trade(
        decision,
        trade_id="paper-risk-001",
        eligibility=broker_eligibility(gate),
    )

    assert trade.filled_quantity == gate.position_size.quantity


def broker_eligibility(gate):
    from app.alerts.approval_workflow import combine_entry_eligibility
    from app.risk.models import SessionGuardDecision

    return combine_entry_eligibility(gate, SessionGuardDecision(True))
