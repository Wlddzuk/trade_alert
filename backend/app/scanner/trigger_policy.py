from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.providers.models import IntradayBar

from .strategy_defaults import StrategyDefaults


def bar_interval_seconds(bar: IntradayBar) -> int:
    if bar.interval_seconds is not None:
        return bar.interval_seconds
    if bar.interval_minutes is None:
        raise ValueError("intraday bar must have an interval")
    return bar.interval_minutes * 60


@dataclass(frozen=True, slots=True)
class TriggerBarSelection:
    bars: tuple[IntradayBar, ...]
    interval_seconds: int
    used_fallback: bool

    @property
    def interval_label(self) -> str:
        return f"{self.interval_seconds}s" if self.interval_seconds < 60 else f"{self.interval_seconds // 60}m"


def resolve_trigger_bars(
    *,
    preferred_bars: Iterable[IntradayBar],
    fallback_bars: Iterable[IntradayBar],
    defaults: StrategyDefaults | None = None,
) -> TriggerBarSelection:
    strategy_defaults = defaults or StrategyDefaults()
    preferred = tuple(
        sorted(
            (bar for bar in preferred_bars if bar_interval_seconds(bar) == strategy_defaults.preferred_trigger_interval_seconds),
            key=lambda bar: bar.start_at,
        )
    )
    if preferred:
        return TriggerBarSelection(
            bars=preferred,
            interval_seconds=strategy_defaults.preferred_trigger_interval_seconds,
            used_fallback=False,
        )

    fallback = tuple(
        sorted(
            (bar for bar in fallback_bars if bar_interval_seconds(bar) == strategy_defaults.fallback_trigger_interval_seconds),
            key=lambda bar: bar.start_at,
        )
    )
    return TriggerBarSelection(
        bars=fallback,
        interval_seconds=strategy_defaults.fallback_trigger_interval_seconds,
        used_fallback=True,
    )
