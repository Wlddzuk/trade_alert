from __future__ import annotations

from app.scanner.models import CandidateRow, LinkedNewsEvent

from .context_features import ContextFeatures
from .news_linking import catalyst_age_seconds, first_news_at
from .strategy_defaults import StrategyDefaults
from .strategy_models import InvalidReason, SetupValidity


def _invalid(
    *,
    evaluated_at,
    first_catalyst_at,
    catalyst_age,
    reason: InvalidReason,
) -> SetupValidity:
    return SetupValidity(
        setup_valid=False,
        evaluated_at=evaluated_at,
        first_catalyst_at=first_catalyst_at,
        catalyst_age_seconds=catalyst_age,
        primary_invalid_reason=reason,
    )


def evaluate_setup_validity(
    row: CandidateRow,
    linked_news: LinkedNewsEvent | None,
    context_features: ContextFeatures,
    *,
    defaults: StrategyDefaults | None = None,
) -> SetupValidity:
    strategy_defaults = defaults or StrategyDefaults()
    first_catalyst_at = first_news_at(linked_news)
    catalyst_age = catalyst_age_seconds(linked_news, observed_at=row.observed_at)

    # Hard gate: must have a catalyst
    if first_catalyst_at is None or catalyst_age is None:
        return _invalid(
            evaluated_at=row.observed_at,
            first_catalyst_at=None,
            catalyst_age=None,
            reason=InvalidReason.MISSING_CATALYST,
        )
    # Hard gate: catalyst must be fresh (< max age)
    if catalyst_age > strategy_defaults.max_catalyst_age_minutes * 60:
        return _invalid(
            evaluated_at=row.observed_at,
            first_catalyst_at=first_catalyst_at,
            catalyst_age=catalyst_age,
            reason=InvalidReason.STALE_CATALYST,
        )
    # Hard gate: minimum day move
    if (
        row.change_from_prior_close_percent is None
        or row.change_from_prior_close_percent < strategy_defaults.min_move_on_day_percent
    ):
        return _invalid(
            evaluated_at=row.observed_at,
            first_catalyst_at=first_catalyst_at,
            catalyst_age=catalyst_age,
            reason=InvalidReason.INSUFFICIENT_DAY_MOVE,
        )

    # Hard gate: minimum daily relative volume
    if (
        row.daily_relative_volume is None
        or row.daily_relative_volume < strategy_defaults.min_daily_relative_volume
    ):
        return _invalid(
            evaluated_at=row.observed_at,
            first_catalyst_at=first_catalyst_at,
            catalyst_age=catalyst_age,
            reason=InvalidReason.INSUFFICIENT_DAILY_RVOL,
        )
    # Hard gate: minimum short-term relative volume
    if (
        row.short_term_relative_volume is None
        or row.short_term_relative_volume < strategy_defaults.min_short_term_relative_volume
    ):
        return _invalid(
            evaluated_at=row.observed_at,
            first_catalyst_at=first_catalyst_at,
            catalyst_age=catalyst_age,
            reason=InvalidReason.INSUFFICIENT_SHORT_TERM_RVOL,
        )
    # Hard gate: pullback must be present (EMA-9-tagged candle, per Ross Cameron rule)
    if context_features.pullback_low is None or context_features.pullback_retracement_percent is None:
        return _invalid(
            evaluated_at=row.observed_at,
            first_catalyst_at=first_catalyst_at,
            catalyst_age=catalyst_age,
            reason=InvalidReason.MISSING_PULLBACK_CONTEXT,
        )
    # Hard gate: pullback depth must sit inside [min, max] retracement window
    if context_features.pullback_retracement_percent < strategy_defaults.min_pullback_retracement_percent:
        return _invalid(
            evaluated_at=row.observed_at,
            first_catalyst_at=first_catalyst_at,
            catalyst_age=catalyst_age,
            reason=InvalidReason.PULLBACK_TOO_SHALLOW,
        )
    if context_features.pullback_retracement_percent > strategy_defaults.max_pullback_retracement_percent:
        return _invalid(
            evaluated_at=row.observed_at,
            first_catalyst_at=first_catalyst_at,
            catalyst_age=catalyst_age,
            reason=InvalidReason.PULLBACK_TOO_DEEP,
        )

    # NOTE: EMA alignment and VWAP position remain soft score modifiers
    # (see strategy_ranking.py). The hard gates above implement the strict
    # Ross-Cameron-style discipline for the IG CFD execution model.

    return SetupValidity(
        setup_valid=True,
        evaluated_at=row.observed_at,
        first_catalyst_at=first_catalyst_at,
        catalyst_age_seconds=catalyst_age,
    )
