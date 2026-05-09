from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.scanner.models import CandidateRow, LinkedNewsEvent

from .context_features import ContextFeatures
from .news_linking import catalyst_age_seconds
from .strategy_defaults import StrategyDefaults
from .strategy_models import SetupValidity


class TriggerInvalidationReason(StrEnum):
    SETUP_INVALID = "setup_invalid"
    CONTRADICTORY_CATALYST = "contradictory_catalyst"
    STALE_CATALYST = "stale_catalyst"
    WEAK_RELATIVE_VOLUME = "weak_relative_volume"
    PULLBACK_TOO_DEEP = "pullback_too_deep"
    PULLBACK_LOW_BROKEN = "pullback_low_broken"
    LOST_INTRADAY_CONTEXT = "lost_intraday_context"
    HALTED = "halted"
    DEAD_MOVE = "dead_move"


@dataclass(frozen=True, slots=True)
class InvalidationDecision:
    invalidated: bool
    reason: TriggerInvalidationReason | None = None

    def __post_init__(self) -> None:
        if self.invalidated and self.reason is None:
            raise ValueError("invalidated decisions must include a reason")
        if not self.invalidated and self.reason is not None:
            raise ValueError("non-invalidated decisions cannot include a reason")


def evaluate_invalidation(
    row: CandidateRow,
    linked_news: LinkedNewsEvent | None,
    context_features: ContextFeatures,
    *,
    setup_validity: SetupValidity,
    defaults: StrategyDefaults | None = None,
    halt_active: bool = False,
    failed_breakout_attempts: int = 0,
) -> InvalidationDecision:
    strategy_defaults = defaults or StrategyDefaults()

    if not setup_validity.setup_valid:
        return InvalidationDecision(True, TriggerInvalidationReason.SETUP_INVALID)
    if linked_news is not None and any(event.is_correction for event in linked_news.related_events):
        return InvalidationDecision(True, TriggerInvalidationReason.CONTRADICTORY_CATALYST)

    catalyst_age = catalyst_age_seconds(linked_news, observed_at=row.observed_at)
    if catalyst_age is not None and catalyst_age > strategy_defaults.max_catalyst_age_minutes * 60:
        return InvalidationDecision(True, TriggerInvalidationReason.STALE_CATALYST)
    if halt_active:
        return InvalidationDecision(True, TriggerInvalidationReason.HALTED)
    if failed_breakout_attempts >= 2:
        return InvalidationDecision(True, TriggerInvalidationReason.DEAD_MOVE)

    # NOTE: RVOL, pullback depth, VWAP/EMA position are now soft score modifiers,
    # not hard invalidation gates. This lets momentum stocks surface even when
    # they don't have "perfect" technical setups.

    return InvalidationDecision(False)
