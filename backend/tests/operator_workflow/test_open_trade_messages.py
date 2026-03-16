from __future__ import annotations

from datetime import UTC, datetime

from app.alerts.models import OpenTradeSnapshot, TradeAdjustedEvent, TradeClosedEvent, TradeOpenedEvent
from app.alerts.telegram_renderer import (
    render_trade_adjusted_message,
    render_trade_closed_message,
    render_trade_opened_message,
)


def _trade() -> OpenTradeSnapshot:
    return OpenTradeSnapshot(
        trade_id="trade-xyz",
        symbol="AKRX",
        opened_at=datetime(2026, 3, 15, 14, 25, tzinfo=UTC),
        entry_price="12.45",
        stop_price="11.95",
        target_price="13.60",
        quantity=800,
    )


def test_render_trade_opened_message_includes_material_context_and_controls() -> None:
    rendered = render_trade_opened_message(
        TradeOpenedEvent(
            trade=_trade(),
            observed_at=datetime(2026, 3, 15, 14, 26, tzinfo=UTC),
            note="paper fill simulated",
        )
    )

    assert "[Trade Opened] AKRX" in rendered.text
    assert "Entry / Stop / Target: 12.45 / 11.95 / 13.6" in rendered.text
    assert "Quantity: 800" in rendered.text
    assert "Note: paper fill simulated" in rendered.text
    assert [button.label for button in rendered.buttons] == ["Close", "Adjust Stop", "Adjust Target"]


def test_render_trade_adjusted_message_uses_new_levels_and_keeps_controls() -> None:
    rendered = render_trade_adjusted_message(
        TradeAdjustedEvent(
            trade=_trade(),
            observed_at=datetime(2026, 3, 15, 14, 28, tzinfo=UTC),
            new_stop_price="12.05",
            note="lock in risk",
        )
    )

    assert "[Trade Adjusted] AKRX" in rendered.text
    assert "Entry / Stop / Target: 12.45 / 12.05 / 13.6" in rendered.text
    assert "Note: lock in risk" in rendered.text
    assert [button.label for button in rendered.buttons] == ["Close", "Adjust Stop", "Adjust Target"]


def test_render_trade_closed_message_summarizes_result_without_controls() -> None:
    rendered = render_trade_closed_message(
        TradeClosedEvent(
            trade=_trade(),
            observed_at=datetime(2026, 3, 15, 14, 35, tzinfo=UTC),
            close_price="13.10",
            reason="target_hit",
            realized_pnl="520.00",
        )
    )

    assert "[Trade Closed] AKRX" in rendered.text
    assert "Close Price: 13.1" in rendered.text
    assert "Reason: target_hit" in rendered.text
    assert "Realized P&L: 520" in rendered.text
    assert rendered.buttons == ()
