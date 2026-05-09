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
    """Momentum-first scoring: float, RVOL, and move size dominate.

    EMA/VWAP/pullback are soft modifiers (bonuses/penalties), not hard gates.
    """
    strategy_defaults = defaults or StrategyDefaults()

    if not setup_validity.setup_valid or (invalidation is not None and invalidation.invalidated):
        score = Decimal("15")
        if row.change_from_prior_close_percent is not None:
            score += min(row.change_from_prior_close_percent, Decimal("20")) / Decimal("4")
        return _clamp_score(score)

    score = Decimal("40")  # base for valid setup

    # ── Float bonus (0–15 pts) — LOW FLOAT is the #1 edge ──
    if row.float_shares is not None:
        f = row.float_shares
        if f <= Decimal("10_000_000"):       # under 10M = ideal
            score += Decimal("15")
        elif f <= Decimal("20_000_000"):     # 10M-20M = great
            score += Decimal("12")
        elif f <= Decimal("50_000_000"):     # 20M-50M = decent
            score += Decimal("8")
        elif f <= Decimal("100_000_000"):    # 50M-100M = ok
            score += Decimal("4")
        # >100M float = no bonus (large cap, harder to move)

    # ── RVOL bonus (0–15 pts) — high volume confirms interest ──
    if row.daily_relative_volume is not None:
        rvol = row.daily_relative_volume
        if rvol >= Decimal("10"):
            score += Decimal("15")
        elif rvol >= Decimal("5"):
            score += Decimal("12")
        elif rvol >= Decimal("3"):
            score += Decimal("8")
        elif rvol >= Decimal("1.5"):
            score += Decimal("4")
        # < 1.5x = no bonus

    # ── Short-term RVOL bonus (0–5 pts) ──
    if row.short_term_relative_volume is not None:
        st_rvol = row.short_term_relative_volume
        if st_rvol >= Decimal("3"):
            score += Decimal("5")
        elif st_rvol >= Decimal("1.5"):
            score += Decimal("3")

    # ── Day move bonus (0–10 pts) ──
    if row.change_from_prior_close_percent is not None:
        move = row.change_from_prior_close_percent
        if move >= Decimal("20"):
            score += Decimal("10")
        elif move >= Decimal("10"):
            score += Decimal("8")
        elif move >= Decimal("5"):
            score += Decimal("5")

    # ── Catalyst freshness bonus (0–5 pts) ──
    if setup_validity.catalyst_age_seconds is not None and strategy_defaults.max_catalyst_age_minutes > 0:
        freshness_window_seconds = float(strategy_defaults.max_catalyst_age_minutes * 60)
        freshness_ratio = max(0.0, 1.0 - (setup_validity.catalyst_age_seconds / freshness_window_seconds))
        score += Decimal(str(round(freshness_ratio * 5, 1)))

    # ── Trend context (soft modifiers, NOT gates) ──
    _has_trend = (
        row.price is not None
        and context_features.vwap is not None
        and context_features.ema_9 is not None
        and context_features.ema_20 is not None
    )
    if _has_trend:
        # Above VWAP = bonus, below = small penalty
        if row.price > context_features.vwap:
            score += Decimal("3")
        else:
            score -= Decimal("3")

        # EMA alignment bonus
        if context_features.ema_9 > context_features.ema_20:
            score += Decimal("3")
        else:
            score -= Decimal("2")
    else:
        score -= Decimal("3")  # missing trend data = slight penalty

    # ── Pullback quality (soft modifier) ──
    retracement = context_features.pullback_retracement_percent
    if retracement is not None:
        if (
            strategy_defaults.min_pullback_retracement_percent
            <= retracement
            <= strategy_defaults.max_pullback_retracement_percent
        ):
            score += Decimal("5")  # ideal pullback range
        elif retracement > strategy_defaults.max_pullback_retracement_percent:
            score -= Decimal("3")  # too deep = slight penalty
    if context_features.pullback_volume_lighter:
        score += Decimal("3")

    # ── Trigger bonus ──
    if trigger_evaluation is not None and trigger_evaluation.triggered:
        score += Decimal("8")
        if trigger_evaluation.bullish_confirmation:
            score += Decimal("3")

    # ── Intelligence layer adjustments ──
    if sentiment_multiplier is not None:
        score = score * sentiment_multiplier

    if adaptive_adjustment is not None:
        score = score + adaptive_adjustment

    return _clamp_score(score)
