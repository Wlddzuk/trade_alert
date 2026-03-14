from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.config import AppConfig
from app.providers.polygon_adapter import PolygonSnapshotProvider
from app.providers.models import DailyBar, IntradayBar, ProviderCapability, ProviderHealthState
from app.scanner.history import MarketHistoryService


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
