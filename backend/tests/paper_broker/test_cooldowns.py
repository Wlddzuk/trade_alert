from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.alerts.approval_workflow import combine_entry_eligibility, approve_with_defaults
from app.paper.broker import PaperBroker
from app.risk.models import (
    RiskDefaults,
    SessionBlockReason,
    SessionState,
    TradeQualitySnapshot,
)
from app.risk.session_guards import evaluate_session_guards
from app.risk.trade_gates import evaluate_trade_gates

from .test_entry_handling import _actionable_alert


def test_session_guards_block_after_single_loss_cooldown() -> None:
    observed_at = datetime(2026, 3, 15, 14, 5, tzinfo=UTC)
    decision = evaluate_session_guards(
        observed_at,
        SessionState(
            account_equity="25000",
            last_loss_at=observed_at - timedelta(minutes=5),
            consecutive_losses=1,
        ),
    )

    assert decision.allowed is False
    assert decision.reason is SessionBlockReason.COOLDOWN_ACTIVE


def test_session_guards_use_longer_cooldown_after_two_losses() -> None:
    observed_at = datetime(2026, 3, 15, 14, 25, tzinfo=UTC)
    decision = evaluate_session_guards(
        observed_at,
        SessionState(
            account_equity="25000",
            last_loss_at=observed_at - timedelta(minutes=20),
            consecutive_losses=2,
        ),
    )

    assert decision.allowed is False
    assert decision.reason is SessionBlockReason.COOLDOWN_ACTIVE
    assert decision.blocked_until == observed_at - timedelta(minutes=20) + timedelta(minutes=30)


def test_session_guards_block_max_daily_loss() -> None:
    decision = evaluate_session_guards(
        datetime(2026, 3, 15, 14, 5, tzinfo=UTC),
        SessionState(
            account_equity="25000",
            realized_pnl_today="-800",
        ),
    )

    assert decision.allowed is False
    assert decision.reason is SessionBlockReason.MAX_DAILY_LOSS_REACHED


def test_session_guards_block_max_open_positions() -> None:
    decision = evaluate_session_guards(
        datetime(2026, 3, 15, 14, 5, tzinfo=UTC),
        SessionState(
            account_equity="25000",
            open_positions=1,
        ),
    )

    assert decision.allowed is False
    assert decision.reason is SessionBlockReason.MAX_OPEN_POSITIONS


def test_session_guards_block_entry_after_cutoff() -> None:
    decision = evaluate_session_guards(
        datetime(2026, 3, 15, 19, 31, tzinfo=UTC),
        SessionState(account_equity="25000"),
    )

    assert decision.allowed is False
    assert decision.reason is SessionBlockReason.ENTRY_CUTOFF_REACHED


def test_broker_rejects_non_actionable_final_entry() -> None:
    broker = PaperBroker()
    decision = approve_with_defaults(_actionable_alert())
    trade_gate = evaluate_trade_gates(
        decision.proposal,
        TradeQualitySnapshot(
            average_daily_volume="900000",
            spread_percent="0.20",
        ),
        account_equity="25000",
    )
    blocked = combine_entry_eligibility(
        trade_gate,
        evaluate_session_guards(
            datetime(2026, 3, 15, 14, 5, tzinfo=UTC),
            SessionState(
                account_equity="25000",
                last_loss_at=datetime(2026, 3, 15, 14, 0, tzinfo=UTC),
                consecutive_losses=1,
            ),
        ),
    )

    with pytest.raises(ValueError, match="actionable entry eligibility"):
        broker.open_trade(
            decision,
            trade_id="paper-cooldown-001",
            eligibility=blocked,
        )
