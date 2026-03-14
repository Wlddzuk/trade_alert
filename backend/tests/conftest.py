from __future__ import annotations

from datetime import UTC, datetime

import pytest


@pytest.fixture
def fixed_received_at() -> datetime:
    return datetime(2026, 3, 13, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def polygon_snapshot_payload() -> dict[str, object]:
    return {
        "status": "OK",
        "tickers": [
            {
                "ticker": "AAPL",
                "updated": 1710331200500,
                "day": {"o": 172.1, "h": 174.25, "l": 171.8, "v": 1543200, "vw": 173.52},
                "prevDay": {"c": 170.45},
                "lastTrade": {"p": 173.95, "t": 1710331200000},
                "min": {"n": 42},
            },
            {
                "ticker": "MSFT",
                "updated": 1710331202500,
                "day": {"o": 410.5, "h": 412.7, "l": 408.2, "v": 802300, "vw": 411.48},
                "prevDay": {"c": 407.11},
                "lastTrade": {"p": 411.86, "t": 1710331202000},
                "min": {"n": 18},
            },
        ],
    }


@pytest.fixture
def benzinga_news_payload() -> list[dict[str, object]]:
    return [
        {
            "id": 700001,
            "title": "Acme Therapeutics rallies after FDA clears trial expansion",
            "body": "<p>Acme Therapeutics said the FDA cleared a trial expansion.</p>",
            "created": "Wed, 13 Mar 2024 14:20:15 -0400",
            "updated": "Wed, 13 Mar 2024 14:22:00 -0400",
            "channels": [{"name": "Biotech"}, {"name": "FDA"}],
            "stocks": [
                {"name": "ACME", "exchange": "NASDAQ"},
                {"name": "IBRX", "exchange": "NASDAQ"},
            ],
            "author": "Benzinga Newsdesk",
            "url": "https://example.com/acme-fda",
        }
    ]
