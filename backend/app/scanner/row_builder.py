from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.providers.models import MarketSnapshot

from .metrics import MarketMetrics
from .models import CandidateRow, LinkedNewsEvent


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    return value.astimezone(UTC)


def _format_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.normalize(), "f")


def has_core_row_fields(
    snapshot: MarketSnapshot,
    linked_news: LinkedNewsEvent | None,
    metrics: MarketMetrics,
) -> bool:
    return (
        linked_news is not None
        and snapshot.last_price is not None
        and metrics.gap_percent is not None
        and metrics.change_from_prior_close_percent is not None
    )


def build_why_surfaced(
    linked_news: LinkedNewsEvent,
    metrics: MarketMetrics,
) -> str:
    parts = [linked_news.catalyst_tag.value]

    change = _format_decimal(metrics.change_from_prior_close_percent)
    if change is not None:
        parts.append(f"move={change}%")

    daily_rvol = _format_decimal(metrics.daily_relative_volume)
    if daily_rvol is not None:
        parts.append(f"daily_rvol={daily_rvol}x")

    return " | ".join(parts)


def build_candidate_row(
    snapshot: MarketSnapshot,
    linked_news: LinkedNewsEvent | None,
    metrics: MarketMetrics,
    *,
    observed_at: datetime | None = None,
) -> CandidateRow | None:
    if linked_news is None or not has_core_row_fields(snapshot, linked_news, metrics):
        return None

    row_observed_at = snapshot.observed_at if observed_at is None else _ensure_aware(observed_at)
    time_since_news = max((row_observed_at - linked_news.latest_event_at).total_seconds(), 0.0)

    return CandidateRow(
        symbol=snapshot.symbol,
        headline=linked_news.headline,
        catalyst_tag=linked_news.catalyst_tag,
        latest_news_at=linked_news.latest_event_at,
        time_since_news_seconds=time_since_news,
        observed_at=row_observed_at,
        price=snapshot.last_price,
        volume=snapshot.session_volume,
        average_daily_volume=metrics.average_daily_volume,
        daily_relative_volume=metrics.daily_relative_volume,
        short_term_relative_volume=metrics.short_term_relative_volume,
        gap_percent=metrics.gap_percent,
        change_from_prior_close_percent=metrics.change_from_prior_close_percent,
        pullback_from_high_percent=metrics.pullback_from_high_percent,
        why_surfaced=build_why_surfaced(linked_news, metrics),
    )
