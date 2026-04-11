from __future__ import annotations

from decimal import Decimal
from dataclasses import dataclass

from .context_features import ContextFeatures
from .invalidation import InvalidationDecision
from .models import CandidateRow
from .strategy_defaults import StrategyDefaults
from .strategy_models import SetupValidity
from .strategy_ranking import score_candidate
from .strategy_tags import StrategyStageTag, derive_stage_tag
from .trigger_logic import TriggerEvaluation


@dataclass(frozen=True, slots=True)
class StrategyProjection:
    row: CandidateRow
    setup_validity: SetupValidity
    score: int
    stage_tag: StrategyStageTag
    supporting_reasons: tuple[str, ...]
    primary_invalid_reason: str | None
    trigger_evaluation: TriggerEvaluation | None = None
    invalidation: InvalidationDecision | None = None

    @property
    def is_valid(self) -> bool:
        return self.setup_validity.setup_valid and not (self.invalidation and self.invalidation.invalidated)


def build_supporting_reasons(
    row: CandidateRow,
    *,
    context_features: ContextFeatures,
    trigger_evaluation: TriggerEvaluation | None = None,
    invalidation: InvalidationDecision | None = None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if invalidation is not None and invalidation.invalidated and invalidation.reason is not None:
        reasons.append(f"invalid={invalidation.reason.value}")
        return tuple(reasons)

    if row.change_from_prior_close_percent is not None:
        reasons.append(f"move={row.change_from_prior_close_percent.normalize()}%")
    if row.daily_relative_volume is not None:
        reasons.append(f"daily_rvol={row.daily_relative_volume.normalize()}x")
    if row.short_term_relative_volume is not None:
        reasons.append(f"short_rvol={row.short_term_relative_volume.normalize()}x")
    if context_features.pullback_volume_lighter:
        reasons.append("lighter_pullback_volume")
    if trigger_evaluation is not None and trigger_evaluation.triggered:
        reasons.append(f"trigger={trigger_evaluation.interval_seconds}s")
        if trigger_evaluation.bullish_confirmation:
            reasons.append("bullish_confirmation")
    return tuple(reasons)


def project_strategy_row(
    row: CandidateRow,
    *,
    context_features: ContextFeatures,
    setup_validity: SetupValidity,
    trigger_evaluation: TriggerEvaluation | None = None,
    invalidation: InvalidationDecision | None = None,
    defaults: StrategyDefaults | None = None,
    sentiment_multiplier: Decimal | None = None,
    adaptive_adjustment: Decimal | None = None,
) -> StrategyProjection:
    stage_tag = derive_stage_tag(
        setup_validity,
        trigger_evaluation=trigger_evaluation,
        invalidation=invalidation,
    )
    score = score_candidate(
        row,
        context_features=context_features,
        setup_validity=setup_validity,
        trigger_evaluation=trigger_evaluation,
        invalidation=invalidation,
        defaults=defaults,
        sentiment_multiplier=sentiment_multiplier,
        adaptive_adjustment=adaptive_adjustment,
    )
    # Prefer the specific setup reason (e.g. "below_vwap", "ema_misalignment")
    # over the generic invalidation wrapper ("setup_invalid") so the dashboard
    # shows WHY the setup failed.
    primary_invalid_reason = None
    if not setup_validity.setup_valid and setup_validity.primary_invalid_reason is not None:
        primary_invalid_reason = setup_validity.primary_invalid_reason.value
    elif invalidation is not None and invalidation.invalidated and invalidation.reason is not None:
        primary_invalid_reason = invalidation.reason.value

    return StrategyProjection(
        row=row,
        setup_validity=setup_validity,
        score=score,
        stage_tag=stage_tag,
        supporting_reasons=build_supporting_reasons(
            row,
            context_features=context_features,
            trigger_evaluation=trigger_evaluation,
            invalidation=invalidation,
        ),
        primary_invalid_reason=primary_invalid_reason,
        trigger_evaluation=trigger_evaluation,
        invalidation=invalidation,
    )

