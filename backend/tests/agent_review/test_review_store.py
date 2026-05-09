from __future__ import annotations

import json
from datetime import UTC, datetime

from app.agents import TradingAgentsReviewResult, TradingAgentsReviewStore


def test_review_store_appends_jsonl_record(tmp_path) -> None:
    path = tmp_path / "reviews.jsonl"
    store = TradingAgentsReviewStore(path=path)
    result = TradingAgentsReviewResult(
        ticker="NVDA",
        trade_date="2026-04-30",
        status="ok",
        decision={"decision": "watch"},
        llm_provider="google",
        deep_model="gemini-2.5-flash",
        quick_model="gemini-2.5-flash",
        reviewed_at=datetime(2026, 4, 30, 12, 0, tzinfo=UTC),
    )

    store.append(result, context={"score": 92, "stage": "trigger_ready"})

    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["result"]["ticker"] == "NVDA"
    assert records[0]["result"]["decision"] == {"decision": "watch"}
    assert records[0]["context"] == {"score": 92, "stage": "trigger_ready"}
