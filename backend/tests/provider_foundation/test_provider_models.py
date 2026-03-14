from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.config import AppConfig
from app.providers.errors import ProviderRateLimitError
from app.providers.models import (
    CatalystTag,
    MarketSnapshot,
    NewsEvent,
    ProviderCapability,
    ProviderHealthSnapshot,
    ProviderHealthState,
)


def test_app_config_reads_provider_credentials_and_defaults() -> None:
    config = AppConfig.from_env(
        {
            "POLYGON_API_KEY": "polygon-key",
            "BENZINGA_API_KEY": "benzinga-key",
            "POLYGON_TIMEOUT_SECONDS": "12.5",
            "BENZINGA_BASE_URL": "https://api.benzinga.com/",
        }
    )

    assert config.polygon.api_key == "polygon-key"
    assert config.polygon.endpoint.timeout_seconds == 12.5
    assert config.polygon.endpoint.base_url == "https://api.polygon.io"
    assert config.benzinga.api_key == "benzinga-key"
    assert config.benzinga.endpoint.base_url == "https://api.benzinga.com"


def test_market_snapshot_coerces_times_to_utc_and_normalizes_values() -> None:
    snapshot = MarketSnapshot(
        symbol=" aapl ",
        provider="Polygon",
        observed_at=datetime(2026, 3, 13, 8, 31, tzinfo=UTC),
        received_at=datetime(2026, 3, 13, 8, 31, 3, tzinfo=UTC),
        last_price="172.45",
        session_volume=120_000,
        previous_close="168.40",
        open_price="169.00",
        high_price="173.25",
        low_price="168.90",
        vwap="171.62",
        exchange=" nasdaq ",
    )

    assert snapshot.symbol == "AAPL"
    assert snapshot.provider == "polygon"
    assert snapshot.last_price == Decimal("172.45")
    assert snapshot.previous_close == Decimal("168.40")
    assert snapshot.exchange == "NASDAQ"


def test_news_event_normalizes_symbols_channels_and_utc_fields() -> None:
    event = NewsEvent(
        event_id=123,
        provider="Benzinga",
        published_at=datetime(2026, 3, 13, 12, 0, tzinfo=UTC),
        received_at=datetime(2026, 3, 13, 12, 0, 10, tzinfo=UTC),
        updated_at=datetime(2026, 3, 13, 12, 1, tzinfo=UTC),
        headline="  Earnings beat drives fresh momentum  ",
        summary="Company beat expectations.",
        symbols=(" aapl ", " msft "),
        channels=("Earnings", "Technology"),
        authors=("Benzinga Newsdesk",),
        catalyst_tag=CatalystTag.EARNINGS,
    )

    assert event.event_id == "123"
    assert event.provider == "benzinga"
    assert event.symbols == ("AAPL", "MSFT")
    assert event.channels == ("Earnings", "Technology")
    assert event.catalyst_tag is CatalystTag.EARNINGS


def test_provider_health_snapshot_tracks_freshness_metadata() -> None:
    now = datetime(2026, 3, 13, 12, 0, tzinfo=UTC)
    health = ProviderHealthSnapshot(
        provider="polygon",
        capability=ProviderCapability.MARKET_DATA,
        observed_at=now,
        last_update_at=now - timedelta(seconds=4),
        freshness_age_seconds=4.0,
        state=ProviderHealthState.HEALTHY,
        reason="streaming",
    )

    assert health.provider == "polygon"
    assert health.capability is ProviderCapability.MARKET_DATA
    assert health.freshness_age_seconds == 4.0


def test_provider_errors_expose_status_and_retriable_flags() -> None:
    error = ProviderRateLimitError("polygon", "rate limited", status_code=429)

    assert str(error) == "rate limited"
    assert error.provider == "polygon"
    assert error.status_code == 429
    assert error.retriable is True


def test_market_snapshot_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="observed_at must be timezone-aware"):
        MarketSnapshot(
            symbol="AAPL",
            provider="polygon",
            observed_at=datetime(2026, 3, 13, 12, 0),
            received_at=datetime(2026, 3, 13, 12, 0, tzinfo=UTC),
            last_price="10",
            session_volume=1,
        )
