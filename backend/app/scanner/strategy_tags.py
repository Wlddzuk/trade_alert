from __future__ import annotations

from enum import StrEnum

from .invalidation import InvalidationDecision
from .trigger_logic import TriggerEvaluation
from .strategy_models import SetupValidity


class StrategyStageTag(StrEnum):
    BUILDING = "building"
    TRIGGER_READY = "trigger_ready"
    INVALIDATED = "invalidated"


def derive_stage_tag(
    setup_validity: SetupValidity,
    trigger_evaluation: TriggerEvaluation | None = None,
    invalidation: InvalidationDecision | None = None,
) -> StrategyStageTag:
    if invalidation is not None and invalidation.invalidated:
        return StrategyStageTag.INVALIDATED
    if not setup_validity.setup_valid:
        return StrategyStageTag.INVALIDATED
    if trigger_evaluation is not None and trigger_evaluation.triggered:
        return StrategyStageTag.TRIGGER_READY
    return StrategyStageTag.BUILDING
