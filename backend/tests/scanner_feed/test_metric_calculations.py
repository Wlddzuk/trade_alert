from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from app.config import AppConfig
from app.providers.polygon_adapter import PolygonSnapshotProvider
from app.providers.models import (
    DailyBar,
    IntradayBar,
    MarketSnapshot,
    ProviderCapability,
    ProviderHealthState,
)
from app.scanner.history import MarketHistoryService
from app.scanner.metrics import build_market_metrics, short_term_relative_volume


def test_polygon_provider_normalizes_daily_bars_through_history_service(
    fixed_received_at: datetime,
) -> None:
    observed_requests: list[tuple[str, dict[str, object]]] = []
    payload = {
        "status": "OK",
        "results": [
            {"t": 1710288000000, "o": 171.2, "h": 174.0, "l": 170.5, "c": 173.4, "v": 1543200},
            {"t": 1710374400000, "o": 173.4, "h": 175.1, "l": 172.8, "c": 174.8, "v": 1634500},
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

    batch = asyncio.run(history.pull_daily_bars([" aapl "], lookback_days=20))

    assert "/v2/aggs/ticker/AAPL/range/1/day/" in observed_requests[0][0]
    assert batch.provider == "polygon"
    assert batch.capability is ProviderCapability.MARKET_DATA
    assert batch.health.state is ProviderHealthState.HEALTHY
    assert isinstance(batch.records[0], DailyBar)
    assert batch.records[0].symbol == "AAPL"
    assert batch.records[0].close_price is not None


def test_polygon_provider_normalizes_intraday_bars_through_history_service(
    fixed_received_at: datetime,
) -> None:
    observed_requests: list[tuple[str, dict[str, object]]] = []
    payload = {
        "status": "OK",
        "results": [
            {"t": 1710331200000, "o": 172.8, "h": 173.2, "l": 172.7, "c": 173.1, "v": 52400},
            {"t": 1710331500000, "o": 173.1, "h": 173.6, "l": 173.0, "c": 173.4, "v": 61200},
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

    batch = asyncio.run(history.pull_intraday_bars(["aapl"], interval_minutes=5, lookback_days=20))

    assert "/v2/aggs/ticker/AAPL/range/5/minute/" in observed_requests[0][0]
    assert batch.provider == "polygon"
    assert batch.capability is ProviderCapability.MARKET_DATA
    assert isinstance(batch.records[0], IntradayBar)
    assert batch.records[0].interval_minutes == 5
    assert batch.health.last_update_at == datetime(2024, 3, 13, 12, 5, tzinfo=UTC)


def test_build_market_metrics_computes_required_fields() -> None:
    snapshot = MarketSnapshot(
        symbol="AAPL",
        provider="polygon",
        observed_at=datetime(2026, 3, 13, 13, 40, tzinfo=UTC),
        received_at=datetime(2026, 3, 13, 13, 40, tzinfo=UTC),
        last_price="12.00",
        session_volume=1_200_000,
        previous_close="10.00",
        open_price="11.00",
        high_price="12.50",
        low_price="10.75",
    )
    daily_bars = (
        DailyBar(
            symbol="AAPL",
            provider="polygon",
            trading_date=datetime(2026, 2, 10, tzinfo=UTC).date(),
            observed_at=datetime(2026, 2, 10, 21, 0, tzinfo=UTC),
            open_price="10.00",
            high_price="10.50",
            low_price="9.90",
            close_price="10.20",
            volume=900_000,
        ),
        DailyBar(
            symbol="AAPL",
            provider="polygon",
            trading_date=datetime(2026, 2, 11, tzinfo=UTC).date(),
            observed_at=datetime(2026, 2, 11, 21, 0, tzinfo=UTC),
            open_price="10.20",
            high_price="10.80",
            low_price="10.10",
            close_price="10.70",
            volume=1_100_000,
        ),
    )
    current_bar = IntradayBar(
        symbol="AAPL",
        provider="polygon",
        start_at=datetime(2026, 3, 13, 13, 35, tzinfo=UTC),
        interval_minutes=5,
        open_price="11.70",
        high_price="12.10",
        low_price="11.65",
        close_price="12.00",
        volume=200_000,
    )
    historical_intraday_bars = (
        IntradayBar(
            symbol="AAPL",
            provider="polygon",
            start_at=datetime(2026, 3, 12, 13, 35, tzinfo=UTC),
            interval_minutes=5,
            open_price="11.10",
            high_price="11.30",
            low_price="11.00",
            close_price="11.20",
            volume=100_000,
        ),
        IntradayBar(
            symbol="AAPL",
            provider="polygon",
            start_at=datetime(2026, 3, 11, 13, 35, tzinfo=UTC),
            interval_minutes=5,
            open_price="10.90",
            high_price="11.00",
            low_price="10.80",
            close_price="10.95",
            volume=100_000,
        ),
    )

    metrics = build_market_metrics(
        snapshot,
        daily_bars=daily_bars,
        current_bar=current_bar,
        historical_intraday_bars=historical_intraday_bars,
        lookback_days=20,
    )

    assert metrics.average_daily_volume == Decimal("1000000")
    assert metrics.daily_relative_volume == Decimal("1.2")
    assert metrics.short_term_relative_volume == Decimal("2")
    assert metrics.gap_percent == Decimal("10.0")
    assert metrics.change_from_prior_close_percent == Decimal("20.0")
    assert metrics.pullback_from_high_percent == Decimal("4.00")


def test_short_term_relative_volume_uses_same_time_of_day_baseline() -> None:
    current_bar = IntradayBar(
        symbol="AAPL",
        provider="polygon",
        start_at=datetime(2026, 3, 13, 13, 35, tzinfo=UTC),
        interval_minutes=5,
        open_price="11.20",
        high_price="11.40",
        low_price="11.10",
        close_price="11.35",
        volume=300_000,
    )
    historical_intraday_bars = (
        IntradayBar(
            symbol="AAPL",
            provider="polygon",
            start_at=datetime(2026, 3, 12, 13, 35, tzinfo=UTC),
            interval_minutes=5,
            open_price="11.00",
            high_price="11.10",
            low_price="10.90",
            close_price="11.05",
            volume=100_000,
        ),
        IntradayBar(
            symbol="AAPL",
            provider="polygon",
            start_at=datetime(2026, 3, 11, 13, 35, tzinfo=UTC),
            interval_minutes=5,
            open_price="10.80",
            high_price="10.90",
            low_price="10.70",
            close_price="10.85",
            volume=200_000,
        ),
        IntradayBar(
            symbol="AAPL",
            provider="polygon",
            start_at=datetime(2026, 3, 11, 13, 40, tzinfo=UTC),
            interval_minutes=5,
            open_price="10.85",
            high_price="10.95",
            low_price="10.75",
            close_price="10.90",
            volume=900_000,
        ),
    )

    assert short_term_relative_volume(current_bar, historical_intraday_bars) == Decimal("2")
