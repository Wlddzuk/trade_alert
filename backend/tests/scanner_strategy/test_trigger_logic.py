from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.config import AppConfig
from app.providers.polygon_adapter import PolygonSnapshotProvider
from app.providers.models import IntradayBar, ProviderCapability, ProviderHealthState
from app.scanner.history import MarketHistoryService
from app.scanner.trigger_policy import resolve_trigger_bars
from app.scanner.trigger_logic import evaluate_first_break_trigger


def test_polygon_provider_normalizes_15_second_bars_through_history_service(
    fixed_received_at: datetime,
) -> None:
    observed_requests: list[tuple[str, dict[str, object]]] = []
    payload = {
        "status": "OK",
        "results": [
            {"t": 1710331200000, "o": 172.8, "h": 173.2, "l": 172.7, "c": 173.1, "v": 5240},
            {"t": 1710331215000, "o": 173.1, "h": 173.6, "l": 173.0, "c": 173.4, "v": 6120},
        ],
    }

    async def fake_fetch(url: str, params: dict[str, object]) -> dict[str, object]:
        observed_requests.append((url, params))
        return payload

    config = AppConfig.from_env({"POLYGON_API_KEY": "polygon-key"})
    provider = PolygonSnapshotProvider(
        config.polygon,
        fetch_json=fake_fetch,
        now_fn=lambda: fixed_received_at,
    )
    history = MarketHistoryService(provider)

    batch = asyncio.run(history.pull_intraday_bars(["aapl"], interval_minutes=None, interval_seconds=15, lookback_days=5))

    assert "/v2/aggs/ticker/AAPL/range/15/second/" in observed_requests[0][0]
    assert batch.provider == "polygon"
    assert batch.capability is ProviderCapability.MARKET_DATA
    assert batch.health.state is ProviderHealthState.HEALTHY
    assert isinstance(batch.records[0], IntradayBar)
    assert batch.records[0].interval_seconds == 15
    assert batch.records[0].interval_unit == "second"


def test_resolve_trigger_bars_prefers_15_second_and_falls_back_to_1_minute() -> None:
    preferred = (
        IntradayBar(
            symbol="AAPL",
            provider="polygon",
            start_at=datetime(2026, 3, 14, 13, 35, tzinfo=UTC),
            interval_seconds=15,
            open_price="11.0",
            high_price="11.2",
            low_price="10.9",
            close_price="11.1",
            volume=20_000,
        ),
    )
    fallback = (
        IntradayBar(
            symbol="AAPL",
            provider="polygon",
            start_at=datetime(2026, 3, 14, 13, 35, tzinfo=UTC),
            interval_minutes=1,
            open_price="11.0",
            high_price="11.3",
            low_price="10.8",
            close_price="11.2",
            volume=80_000,
        ),
    )

    selected = resolve_trigger_bars(preferred_bars=preferred, fallback_bars=fallback)
    assert selected.interval_seconds == 15
    assert selected.used_fallback is False
    assert selected.bars == preferred

    fallback_only = resolve_trigger_bars(preferred_bars=(), fallback_bars=fallback)
    assert fallback_only.interval_seconds == 60
    assert fallback_only.used_fallback is True
    assert fallback_only.bars == fallback


def test_evaluate_first_break_trigger_uses_first_intrabar_break_without_requiring_bullish_close() -> None:
    bars = (
        IntradayBar(
            symbol="AAPL",
            provider="polygon",
            start_at=datetime(2026, 3, 14, 13, 35, tzinfo=UTC),
            interval_seconds=15,
            open_price="10.00",
            high_price="10.20",
            low_price="9.90",
            close_price="10.10",
            volume=5_000,
        ),
        IntradayBar(
            symbol="AAPL",
            provider="polygon",
            start_at=datetime(2026, 3, 14, 13, 35, 15, tzinfo=UTC),
            interval_seconds=15,
            open_price="10.30",
            high_price="10.40",
            low_price="10.00",
            close_price="10.15",
            volume=6_000,
        ),
        IntradayBar(
            symbol="AAPL",
            provider="polygon",
            start_at=datetime(2026, 3, 14, 13, 35, 30, tzinfo=UTC),
            interval_seconds=15,
            open_price="10.10",
            high_price="10.35",
            low_price="10.00",
            close_price="10.30",
            volume=7_000,
        ),
    )
    selection = resolve_trigger_bars(preferred_bars=bars, fallback_bars=())

    evaluation = evaluate_first_break_trigger(selection)

    assert evaluation.triggered is True
    assert evaluation.trigger_price == bars[0].high_price
    assert evaluation.trigger_bar_started_at == bars[1].start_at
    assert evaluation.interval_seconds == 15
    assert evaluation.bullish_confirmation is False
