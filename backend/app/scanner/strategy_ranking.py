from __future__ import annotations

from decimal import Decimal

from .context_features import ContextFeatures
from .invalidation import InvalidationDecision
from .models import CandidateRow
from .strategy_defaults import StrategyDefaults
from .strategy_models import SetupValidity
from .trigger_logic import TriggerEvaluation


def _clamp_score(value: Decimal) -> int:
    return max(0, min(100, int(value.quantize(Decimal("1")))))


def score_candidate(
    row: CandidateRow,
    *,
    context_features: ContextFeatures,
    setup_validity: SetupValidity,
    trigger_evaluation: TriggerEvaluation | None = None,
    invalidation: InvalidationDecision | None = None,
    defaults: StrategyDefaults | None = None,
    sentiment_multiplier: Decimal | None = None,
    adaptive_adjustment: Decimal | None = None,
) -> int:
    """Score a candidate row with optional LLM sentiment and adaptive learning adjustments.

    The scoring pipeline is:
    1. Compute raw rule-based score (0–100)
    2. Apply sentiment multiplier (0.5x–1.5x) from LLM analysis
    3. Add adaptive adjustment points (±15) from historical learning
    4. Clamp final result to 0–100
    """
    strategy_defaults = defaults or StrategyDefaults()

    if not setup_validity.setup_valid or (invalidation is not None and invalidation.invalidated):
        score = Decimal("15")
        if row.change_from_prior_close_percent is not None:
            score += min(row.change_from_prior_close_percent, Decimal("20")) / Decimal("4")
        return _clamp_score(score)

    score = Decimal("55")
    if setup_validity.catalyst_age_seconds is not None and strategy_defaults.max_catalyst_age_minutes > 0:
        freshness_window_seconds = float(strategy_defaults.max_catalyst_age_minutes * 60)
        freshness_ratio = max(0.0, 1.0 - (setup_validity.catalyst_age_seconds / freshness_window_seconds))
        score += Decimal(str(freshness_ratio * 5))
    if row.change_from_prior_close_percent is not None:
        move_bonus = max(row.change_from_prior_close_percent - strategy_defaults.min_move_on_day_percent, Decimal("0"))
        score += min(move_bonus, Decimal("20")) / Decimal("2")
    if row.daily_relative_volume is not None:
        daily_bonus = max(row.daily_relative_volume - strategy_defaults.min_daily_relative_volume, Decimal("0"))
        score += min(daily_bonus * Decimal("5"), Decimal("10"))
    if row.short_term_relative_volume is not None:
        short_term_bonus = max(
            row.short_term_relative_volume - strategy_defaults.min_short_term_relative_volume,
            Decimal("0"),
        )
        score += min(short_term_bonus * Decimal("5"), Decimal("10"))
    if context_features.pullback_retracement_percent is not None:
        if (
            strategy_defaults.min_pullback_retracement_percent
            <= context_features.pullback_retracement_percent
            <= strategy_defaults.max_pullback_retracement_percent
        ):
            score += Decimal("8")
    if context_features.pullback_volume_lighter:
        score += Decimal("4")
    if trigger_evaluation is not None and trigger_evaluation.triggered:
        score += Decimal("8")
        if trigger_evaluation.bullish_confirmation:
            score += Decimal("3")

    # ── Intelligence layer adjustments ──────────────────────────────
    # Apply LLM sentiment multiplier (scales score by 0.5x to 1.5x)
    if sentiment_multiplier is not None:
        score = score * sentiment_multiplier

    # Apply adaptive learning adjustment (adds/subtracts up to ±15 points)
    if adaptive_adjustment is not None:
        score = score + adaptive_adjustment

    return _clamp_score(score)
