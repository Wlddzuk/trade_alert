from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .tradingagents_reviewer import TradingAgentsReviewResult

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_REVIEW_LOG_PATH = _BACKEND_DIR / "data" / "tradingagents" / "agent_reviews.jsonl"


@dataclass(frozen=True, slots=True)
class TradingAgentsReviewStore:
    path: Path = field(default_factory=lambda: _DEFAULT_REVIEW_LOG_PATH)

    def append(
        self,
        result: TradingAgentsReviewResult,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": datetime.now(UTC).isoformat(),
            "result": result.to_dict(),
            "context": dict(context or {}),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str, ensure_ascii=True))
            handle.write("\n")
