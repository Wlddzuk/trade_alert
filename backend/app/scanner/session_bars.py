from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.providers.models import IntradayBar


MARKET_TIMEZONE = ZoneInfo("America/New_York")


def session_date_for(value: datetime, *, market_tz: ZoneInfo = MARKET_TIMEZONE) -> date:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("session datetime must be timezone-aware")
    return value.astimezone(market_tz).date()


def bars_for_session(
    bars: Iterable[IntradayBar],
    *,
    as_of: datetime,
    market_tz: ZoneInfo = MARKET_TIMEZONE,
) -> tuple[IntradayBar, ...]:
    target_session = session_date_for(as_of, market_tz=market_tz)
    return tuple(
        sorted(
            (
                bar
                for bar in bars
                if session_date_for(bar.start_at, market_tz=market_tz) == target_session
            ),
            key=lambda bar: bar.start_at,
        )
    )


def bars_before_session(
    bars: Iterable[IntradayBar],
    *,
    as_of: datetime,
    market_tz: ZoneInfo = MARKET_TIMEZONE,
) -> tuple[IntradayBar, ...]:
    target_session = session_date_for(as_of, market_tz=market_tz)
    return tuple(
        sorted(
            (
                bar
                for bar in bars
                if session_date_for(bar.start_at, market_tz=market_tz) < target_session
            ),
            key=lambda bar: bar.start_at,
        )
    )
