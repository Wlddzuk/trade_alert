from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.ops.health_models import SystemTrustSnapshot, SystemTrustState
from app.runtime.session_window import RuntimeWindow
from app.scanner.feed_service import CandidateFeedService
from app.scanner.feed_store import CandidateFeedConfig, CandidateFeedStore
from app.scanner.models import CandidateRow
from app.providers.models import CatalystTag


def _candidate_row(
    symbol: str,
    *,
    latest_news_at: datetime,
    observed_at: datetime,
    change_percent: str,
    price: str = "12.00",
) -> CandidateRow:
    return CandidateRow(
        symbol=symbol,
        headline=f"{symbol} headline",
        catalyst_tag=CatalystTag.GENERAL,
        latest_news_at=latest_news_at,
        time_since_news_seconds=max((observed_at - latest_news_at).total_seconds(), 0.0),
        observed_at=observed_at,
        price=Decimal(price),
        volume=1_200_000,
        average_daily_volume=Decimal("1000000"),
        daily_relative_volume=Decimal("1.2"),
        short_term_relative_volume=Decimal("2"),
        gap_percent=Decimal("10.0"),
        change_from_prior_close_percent=Decimal(change_percent),
        pullback_from_high_percent=Decimal("4.00"),
        why_surfaced="general | move=20% | daily_rvol=1.2x",
    )


def _trust_snapshot(
    observed_at: datetime,
    *,
    actionable: bool,
    trust_state: SystemTrustState,
) -> SystemTrustSnapshot:
    runtime_state = RuntimeWindow().status_at(observed_at)
    return SystemTrustSnapshot(
        observed_at=runtime_state.observed_at_utc,
        trust_state=trust_state,
        actionable=actionable,
        runtime_state=runtime_state,
        provider_statuses=(),
        reasons=(),
    )


def test_feed_store_updates_in_place_and_expires_inactive_rows() -> None:
    store = CandidateFeedStore(CandidateFeedConfig(inactivity_timeout_seconds=300))
    first = _candidate_row(
        "AAPL",
        latest_news_at=datetime(2026, 3, 13, 13, 35, tzinfo=UTC),
        observed_at=datetime(2026, 3, 13, 13, 40, tzinfo=UTC),
        change_percent="20.0",
    )
    updated = _candidate_row(
        "AAPL",
        latest_news_at=datetime(2026, 3, 13, 13, 37, tzinfo=UTC),
        observed_at=datetime(2026, 3, 13, 13, 42, tzinfo=UTC),
        change_percent="24.0",
        price="12.40",
    )

    store.upsert(first)
    store.upsert(updated)

    rows = store.rows()
    assert len(rows) == 1
    assert rows[0].price == Decimal("12.40")

    expired = store.expire_inactive(datetime(2026, 3, 13, 13, 48, 1, tzinfo=UTC))
    assert expired == ("AAPL",)
    assert store.rows() == ()


def test_feed_service_orders_by_freshest_news_then_move() -> None:
    service = CandidateFeedService()
    rows = (
        _candidate_row(
            "MSFT",
            latest_news_at=datetime(2026, 3, 13, 13, 36, tzinfo=UTC),
            observed_at=datetime(2026, 3, 13, 13, 40, tzinfo=UTC),
            change_percent="18.0",
        ),
        _candidate_row(
            "AAPL",
            latest_news_at=datetime(2026, 3, 13, 13, 38, tzinfo=UTC),
            observed_at=datetime(2026, 3, 13, 13, 40, tzinfo=UTC),
            change_percent="16.0",
        ),
        _candidate_row(
            "NVDA",
            latest_news_at=datetime(2026, 3, 13, 13, 38, tzinfo=UTC),
            observed_at=datetime(2026, 3, 13, 13, 40, tzinfo=UTC),
            change_percent="22.0",
        ),
    )

    snapshot = service.refresh(
        rows,
        trust_snapshot=_trust_snapshot(
            datetime(2026, 3, 13, 13, 40, tzinfo=UTC),
            actionable=True,
            trust_state=SystemTrustState.HEALTHY,
        ),
    )

    assert [row.symbol for row in snapshot.rows] == ["NVDA", "AAPL", "MSFT"]


def test_feed_service_suppresses_updates_when_trust_not_actionable() -> None:
    service = CandidateFeedService()
    existing = _candidate_row(
        "AAPL",
        latest_news_at=datetime(2026, 3, 13, 13, 35, tzinfo=UTC),
        observed_at=datetime(2026, 3, 13, 13, 40, tzinfo=UTC),
        change_percent="20.0",
    )
    service.refresh(
        (existing,),
        trust_snapshot=_trust_snapshot(
            datetime(2026, 3, 13, 13, 40, tzinfo=UTC),
            actionable=True,
            trust_state=SystemTrustState.HEALTHY,
        ),
    )

    suppressed = service.refresh(
        (
            _candidate_row(
                "MSFT",
                latest_news_at=datetime(2026, 3, 13, 13, 41, tzinfo=UTC),
                observed_at=datetime(2026, 3, 13, 13, 42, tzinfo=UTC),
                change_percent="25.0",
            ),
        ),
        trust_snapshot=_trust_snapshot(
            datetime(2026, 3, 13, 13, 42, tzinfo=UTC),
            actionable=False,
            trust_state=SystemTrustState.DEGRADED,
        ),
    )

    assert [row.symbol for row in suppressed.rows] == ["AAPL"]
    assert suppressed.actionable is False


def test_feed_service_carries_active_rows_across_regular_open() -> None:
    service = CandidateFeedService(CandidateFeedStore(CandidateFeedConfig(inactivity_timeout_seconds=600)))
    premarket_row = _candidate_row(
        "AAPL",
        latest_news_at=datetime(2026, 3, 13, 13, 25, tzinfo=UTC),
        observed_at=datetime(2026, 3, 13, 13, 29, tzinfo=UTC),
        change_percent="20.0",
    )

    service.refresh(
        (premarket_row,),
        trust_snapshot=_trust_snapshot(
            datetime(2026, 3, 13, 13, 29, tzinfo=UTC),
            actionable=True,
            trust_state=SystemTrustState.HEALTHY,
        ),
    )
    carryover = service.refresh(
        (),
        trust_snapshot=_trust_snapshot(
            datetime(2026, 3, 13, 13, 31, tzinfo=UTC),
            actionable=True,
            trust_state=SystemTrustState.HEALTHY,
        ),
    )

    assert [row.symbol for row in carryover.rows] == ["AAPL"]
