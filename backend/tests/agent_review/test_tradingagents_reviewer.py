from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.agents.tradingagents_reviewer import (
    TradingAgentsReviewConfig,
    TradingAgentsReviewer,
)


class FakeTradingAgent:
    def __init__(self, decision: dict[str, str] | None = None) -> None:
        self.decision = decision or {"decision": "watch"}
        self.calls: list[tuple[str, str]] = []

    def propagate(self, ticker: str, trade_date: str) -> tuple[dict[str, str], dict[str, str]]:
        self.calls.append((ticker, trade_date))
        return {"state": "done"}, self.decision


def test_config_defaults_to_gemini_flash_and_yfinance() -> None:
    config = TradingAgentsReviewConfig.from_env({})

    trading_config = config.to_tradingagents_config({"existing": "kept"})

    assert trading_config["existing"] == "kept"
    assert trading_config["llm_provider"] == "google"
    assert trading_config["deep_think_llm"] == "gemini-2.5-flash"
    assert trading_config["quick_think_llm"] == "gemini-2.5-flash"
    assert trading_config["max_debate_rounds"] == 1
    assert trading_config["max_risk_discuss_rounds"] == 1
    assert trading_config["data_vendors"] == {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    }


def test_config_reads_low_cost_overrides(tmp_path: Path) -> None:
    config = TradingAgentsReviewConfig.from_env(
        {
            "TRADINGAGENTS_LLM_PROVIDER": "openrouter",
            "TRADINGAGENTS_MODEL": "moonshotai/kimi-k2.5",
            "TRADINGAGENTS_MAX_REVIEWS_PER_DAY": "3",
            "TRADINGAGENTS_BACKEND_URL": "https://example.test/v1",
            "TRADINGAGENTS_STORAGE_DIR": str(tmp_path),
        }
    )

    trading_config = config.to_tradingagents_config({})

    assert trading_config["llm_provider"] == "openrouter"
    assert trading_config["deep_think_llm"] == "moonshotai/kimi-k2.5"
    assert trading_config["quick_think_llm"] == "moonshotai/kimi-k2.5"
    assert trading_config["backend_url"] == "https://example.test/v1"
    assert config.max_reviews_per_day == 3
    assert config.results_dir == tmp_path / "results"
    assert config.data_cache_dir == tmp_path / "cache"
    assert config.memory_log_path == tmp_path / "memory" / "trading_memory.md"


def test_review_normalizes_ticker_and_caches_result(tmp_path: Path) -> None:
    fake_agent = FakeTradingAgent({"decision": "approve"})

    def factory(config: dict[str, Any], debug: bool) -> FakeTradingAgent:
        assert config["llm_provider"] == "google"
        assert debug is False
        return fake_agent

    reviewer = TradingAgentsReviewer(
        TradingAgentsReviewConfig(results_dir=tmp_path / "results", data_cache_dir=tmp_path / "cache"),
        agent_factory=factory,
    )

    first = reviewer.review(" nvda ", "2026-04-30")
    second = reviewer.review("NVDA", "2026-04-30")

    assert first.status == "ok"
    assert first.ticker == "NVDA"
    assert first.decision == {"decision": "approve"}
    assert first.cached is False
    assert second.cached is True
    assert second.decision == first.decision
    assert fake_agent.calls == [("NVDA", "2026-04-30")]


def test_review_respects_daily_cap(tmp_path: Path) -> None:
    fake_agent = FakeTradingAgent()
    reviewer = TradingAgentsReviewer(
        TradingAgentsReviewConfig(
            max_reviews_per_day=1,
            results_dir=tmp_path / "results",
            data_cache_dir=tmp_path / "cache",
        ),
        agent_factory=lambda _config, _debug: fake_agent,
    )

    first = reviewer.review("NVDA", "2026-04-30")
    second = reviewer.review("TSLA", "2026-04-30")

    assert first.status == "ok"
    assert second.status == "skipped"
    assert second.error == "daily TradingAgents review cap reached"
    assert fake_agent.calls == [("NVDA", "2026-04-30")]


def test_review_returns_clear_error_when_provider_key_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    reviewer = TradingAgentsReviewer(
        TradingAgentsReviewConfig(results_dir=tmp_path / "results", data_cache_dir=tmp_path / "cache"),
        default_config={},
    )

    result = reviewer.review("NVDA", "2026-04-30")

    assert result.status == "error"
    assert result.decision is None
    assert result.error is not None
    assert result.error == "missing GOOGLE_API_KEY or GEMINI_API_KEY for TradingAgents provider 'google'"


def test_review_rejects_empty_ticker() -> None:
    reviewer = TradingAgentsReviewer(agent_factory=lambda _config, _debug: FakeTradingAgent())

    with pytest.raises(ValueError, match="ticker must not be empty"):
        reviewer.review(" ")
