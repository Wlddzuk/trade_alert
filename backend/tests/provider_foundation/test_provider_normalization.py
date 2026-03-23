from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.config import AppConfig
from app.ingest.market_ingestor import MarketIngestor
from app.ingest.news_ingestor import NewsIngestor
from app.providers.benzinga_adapter import BenzingaNewsProvider
from app.providers.errors import ProviderTransportError
from app.providers.polygon_adapter import PolygonSnapshotProvider
from app.providers.models import (
    CatalystTag,
    ProviderCapability,
    ProviderHealthState,
)


def test_polygon_provider_normalizes_payloads_through_market_ingestor(
    polygon_snapshot_payload: dict[str, object],
    fixed_received_at: datetime,
) -> None:
    observed_requests: list[tuple[str, dict[str, object]]] = []

    async def fake_fetch(url: str, params: dict[str, object]) -> dict[str, object]:
        observed_requests.append((url, params))
        return polygon_snapshot_payload

    config = AppConfig.from_env({"POLYGON_API_KEY": "polygon-key"})
    provider = PolygonSnapshotProvider(
        config.polygon,
        fetch_json=fake_fetch,
        now_fn=lambda: fixed_received_at,
    )
    ingestor = MarketIngestor(provider)

    batch = asyncio.run(ingestor.pull_latest([" aapl ", "msft"]))

    assert observed_requests[0][0].endswith("/v2/snapshot/locale/us/markets/stocks/tickers")
    assert observed_requests[0][1]["ticker.any_of"] == "AAPL,MSFT"
    assert batch.provider == "polygon"
    assert batch.capability is ProviderCapability.MARKET_DATA
    assert len(batch.records) == 2
    first = batch.records[0]
    assert first.symbol == "AAPL"
    assert first.last_price == Decimal("173.95")
    assert batch.health.state is ProviderHealthState.HEALTHY
    assert batch.health.last_update_at == datetime(2024, 3, 13, 12, 0, 2, tzinfo=UTC)


def test_benzinga_provider_normalizes_payloads_through_news_ingestor(
    benzinga_news_payload: list[dict[str, object]],
    fixed_received_at: datetime,
) -> None:
    observed_requests: list[tuple[str, dict[str, object]]] = []

    async def fake_fetch(url: str, params: dict[str, object]) -> list[dict[str, object]]:
        observed_requests.append((url, params))
        return benzinga_news_payload

    config = AppConfig.from_env({"BENZINGA_API_KEY": "benzinga-key"})
    provider = BenzingaNewsProvider(
        config.benzinga,
        fetch_json=fake_fetch,
        now_fn=lambda: fixed_received_at,
    )
    ingestor = NewsIngestor(provider)

    updated_since = datetime(2026, 3, 13, 11, 30, tzinfo=UTC)
    batch = asyncio.run(
        ingestor.pull_recent([" acme "], updated_since=updated_since, limit=25)
    )

    assert observed_requests[0][0].endswith("/api/v2/news")
    assert observed_requests[0][1]["tickers"] == "ACME"
    assert observed_requests[0][1]["pageSize"] == 25
    assert observed_requests[0][1]["updatedSince"] == int(updated_since.timestamp())
    assert batch.provider == "benzinga"
    assert batch.capability is ProviderCapability.NEWS
    assert len(batch.records) == 1
    event = batch.records[0]
    assert event.symbols == ("ACME", "IBRX")
    assert event.summary == "Acme Therapeutics said the FDA cleared a trial expansion."
    assert event.catalyst_tag is CatalystTag.FDA
    assert batch.health.state is ProviderHealthState.HEALTHY


def test_polygon_provider_translates_fetcher_timeouts() -> None:
    async def fake_fetch(url: str, params: dict[str, object]) -> dict[str, object]:
        raise TimeoutError("socket timeout")

    config = AppConfig.from_env({"POLYGON_API_KEY": "polygon-key"})
    provider = PolygonSnapshotProvider(config.polygon, fetch_json=fake_fetch)

    with pytest.raises(ProviderTransportError, match="polygon request timed out"):
        asyncio.run(provider.fetch_market_snapshots(["AAPL"]))
