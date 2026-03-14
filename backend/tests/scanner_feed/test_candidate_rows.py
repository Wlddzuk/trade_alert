from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.providers.models import CatalystTag, MarketSnapshot, NewsEvent
from app.scanner.metrics import MarketMetrics
from app.scanner.news_linking import latest_news_by_symbol, latest_news_for_symbol
from app.scanner.row_builder import build_candidate_row


def test_latest_news_linking_uses_latest_related_headline_per_symbol() -> None:
    events = (
        NewsEvent(
            event_id="1",
            provider="benzinga",
            published_at=datetime(2026, 3, 13, 13, 0, tzinfo=UTC),
            received_at=datetime(2026, 3, 13, 13, 0, tzinfo=UTC),
            headline="AAPL rallies on initial catalyst",
            symbols=("AAPL",),
            catalyst_tag=CatalystTag.BREAKING_NEWS,
        ),
        NewsEvent(
            event_id="2",
            provider="benzinga",
            published_at=datetime(2026, 3, 13, 13, 5, tzinfo=UTC),
            received_at=datetime(2026, 3, 13, 13, 5, tzinfo=UTC),
            headline="AAPL extends after follow-up update",
            symbols=("AAPL",),
            catalyst_tag=CatalystTag.GENERAL,
        ),
        NewsEvent(
            event_id="3",
            provider="benzinga",
            published_at=datetime(2026, 3, 13, 13, 3, tzinfo=UTC),
            received_at=datetime(2026, 3, 13, 13, 3, tzinfo=UTC),
            headline="MSFT moves on separate headline",
            symbols=("MSFT",),
            catalyst_tag=CatalystTag.GENERAL,
        ),
    )

    latest = latest_news_for_symbol("AAPL", events)
    assert latest is not None
    assert latest.headline == "AAPL extends after follow-up update"
    assert latest.catalyst_tag is CatalystTag.GENERAL
    assert len(latest.related_events) == 2

    by_symbol = latest_news_by_symbol(events)
    assert by_symbol["AAPL"].headline == "AAPL extends after follow-up update"
    assert by_symbol["MSFT"].headline == "MSFT moves on separate headline"


def test_build_candidate_row_emits_required_phase_two_fields() -> None:
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
    latest_news = NewsEvent(
        event_id="2",
        provider="benzinga",
        published_at=datetime(2026, 3, 13, 13, 35, tzinfo=UTC),
        received_at=datetime(2026, 3, 13, 13, 35, tzinfo=UTC),
        headline="AAPL extends after follow-up update",
        symbols=("AAPL",),
        catalyst_tag=CatalystTag.GENERAL,
    )
    linked_news = latest_news_for_symbol("AAPL", (latest_news,))
    metrics = MarketMetrics(
        average_daily_volume=Decimal("1000000"),
        daily_relative_volume=Decimal("1.2"),
        short_term_relative_volume=Decimal("2"),
        gap_percent=Decimal("10.0"),
        change_from_prior_close_percent=Decimal("20.0"),
        pullback_from_high_percent=Decimal("4.00"),
    )

    row = build_candidate_row(snapshot, linked_news, metrics)

    assert row is not None
    assert row.symbol == "AAPL"
    assert row.headline == "AAPL extends after follow-up update"
    assert row.catalyst_tag is CatalystTag.GENERAL
    assert row.time_since_news_seconds == 300.0
    assert row.price == Decimal("12.00")
    assert row.volume == 1_200_000
    assert row.average_daily_volume == Decimal("1000000")
    assert row.daily_relative_volume == Decimal("1.2")
    assert row.short_term_relative_volume == Decimal("2")
    assert row.gap_percent == Decimal("10.0")
    assert row.change_from_prior_close_percent == Decimal("20.0")
    assert row.pullback_from_high_percent == Decimal("4.00")
    assert "general" in row.why_surfaced
    assert "move=20" in row.why_surfaced


def test_build_candidate_row_returns_none_without_core_move_context() -> None:
    snapshot = MarketSnapshot(
        symbol="AAPL",
        provider="polygon",
        observed_at=datetime(2026, 3, 13, 13, 40, tzinfo=UTC),
        received_at=datetime(2026, 3, 13, 13, 40, tzinfo=UTC),
        last_price="12.00",
        session_volume=1_200_000,
    )
    latest_news = NewsEvent(
        event_id="2",
        provider="benzinga",
        published_at=datetime(2026, 3, 13, 13, 35, tzinfo=UTC),
        received_at=datetime(2026, 3, 13, 13, 35, tzinfo=UTC),
        headline="AAPL extends after follow-up update",
        symbols=("AAPL",),
        catalyst_tag=CatalystTag.GENERAL,
    )
    linked_news = latest_news_for_symbol("AAPL", (latest_news,))
    metrics = MarketMetrics(
        average_daily_volume=Decimal("1000000"),
        daily_relative_volume=Decimal("1.2"),
        short_term_relative_volume=Decimal("2"),
        gap_percent=None,
        change_from_prior_close_percent=None,
        pullback_from_high_percent=Decimal("4.00"),
    )

    assert build_candidate_row(snapshot, linked_news, metrics) is None
