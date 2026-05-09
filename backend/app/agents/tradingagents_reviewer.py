from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_STORAGE_DIR = _BACKEND_DIR / "data" / "tradingagents"
_WORKSPACE_DIR = _BACKEND_DIR.parent.parent
_DEFAULT_REPO_PATH = _WORKSPACE_DIR / "_external" / "TradingAgents"

_DEFAULT_DATA_VENDORS = {
    "core_stock_apis": "yfinance",
    "technical_indicators": "yfinance",
    "fundamental_data": "yfinance",
    "news_data": "yfinance",
}

_PROVIDER_KEY_ENV_VARS = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "azure": ("AZURE_OPENAI_API_KEY",),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "glm": ("ZHIPU_API_KEY",),
    "google": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    "openai": ("OPENAI_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "qwen": ("DASHSCOPE_API_KEY",),
    "xai": ("XAI_API_KEY",),
}

AgentFactory = Callable[[dict[str, Any], bool], Any]


class TradingAgentsUnavailableError(RuntimeError):
    """Raised when the optional TradingAgents dependency is not available."""


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _required_positive_int(value: str, *, field_name: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return parsed


def _optional_path(value: str | None) -> Path | None:
    cleaned = _clean_optional(value)
    if cleaned is None:
        return None
    return Path(cleaned).expanduser()


def _default_tradingagents_repo_path() -> Path | None:
    return _DEFAULT_REPO_PATH if _DEFAULT_REPO_PATH.exists() else None


def _normalize_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("ticker must not be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class TradingAgentsReviewConfig:
    """Cost-controlled TradingAgents runtime configuration.

    The defaults deliberately use Gemini Flash and yfinance so the reviewer can
    be tested cheaply before it is connected to any automated workflow.
    """

    llm_provider: str = "google"
    deep_model: str = "gemini-2.5-flash"
    quick_model: str = "gemini-2.5-flash"
    max_debate_rounds: int = 1
    max_risk_discuss_rounds: int = 1
    max_recur_limit: int = 40
    max_reviews_per_day: int = 10
    output_language: str = "English"
    backend_url: str | None = None
    tradingagents_repo_path: Path | None = field(default_factory=_default_tradingagents_repo_path)
    results_dir: Path = field(default_factory=lambda: _DEFAULT_STORAGE_DIR / "results")
    data_cache_dir: Path = field(default_factory=lambda: _DEFAULT_STORAGE_DIR / "cache")
    memory_log_path: Path = field(default_factory=lambda: _DEFAULT_STORAGE_DIR / "memory" / "trading_memory.md")
    data_vendors: Mapping[str, str] = field(default_factory=lambda: dict(_DEFAULT_DATA_VENDORS))

    def __post_init__(self) -> None:
        if self.max_debate_rounds <= 0:
            raise ValueError("max_debate_rounds must be greater than zero")
        if self.max_risk_discuss_rounds <= 0:
            raise ValueError("max_risk_discuss_rounds must be greater than zero")
        if self.max_recur_limit <= 0:
            raise ValueError("max_recur_limit must be greater than zero")
        if self.max_reviews_per_day <= 0:
            raise ValueError("max_reviews_per_day must be greater than zero")
        object.__setattr__(self, "llm_provider", self.llm_provider.strip() or "google")
        object.__setattr__(self, "deep_model", self.deep_model.strip() or "gemini-2.5-flash")
        object.__setattr__(self, "quick_model", self.quick_model.strip() or self.deep_model)
        object.__setattr__(self, "output_language", self.output_language.strip() or "English")
        object.__setattr__(self, "backend_url", _clean_optional(self.backend_url))
        object.__setattr__(self, "data_vendors", dict(self.data_vendors))

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "TradingAgentsReviewConfig":
        model = _clean_optional(env.get("TRADINGAGENTS_MODEL"))
        storage_dir = _optional_path(env.get("TRADINGAGENTS_STORAGE_DIR")) or _DEFAULT_STORAGE_DIR

        return cls(
            llm_provider=_clean_optional(env.get("TRADINGAGENTS_LLM_PROVIDER")) or "google",
            deep_model=_clean_optional(env.get("TRADINGAGENTS_DEEP_MODEL")) or model or "gemini-2.5-flash",
            quick_model=(
                _clean_optional(env.get("TRADINGAGENTS_QUICK_MODEL"))
                or model
                or _clean_optional(env.get("TRADINGAGENTS_DEEP_MODEL"))
                or "gemini-2.5-flash"
            ),
            max_debate_rounds=_required_positive_int(
                env.get("TRADINGAGENTS_MAX_DEBATE_ROUNDS", "1"),
                field_name="TRADINGAGENTS_MAX_DEBATE_ROUNDS",
            ),
            max_risk_discuss_rounds=_required_positive_int(
                env.get("TRADINGAGENTS_MAX_RISK_DISCUSS_ROUNDS", "1"),
                field_name="TRADINGAGENTS_MAX_RISK_DISCUSS_ROUNDS",
            ),
            max_recur_limit=_required_positive_int(
                env.get("TRADINGAGENTS_MAX_RECUR_LIMIT", "40"),
                field_name="TRADINGAGENTS_MAX_RECUR_LIMIT",
            ),
            max_reviews_per_day=_required_positive_int(
                env.get("TRADINGAGENTS_MAX_REVIEWS_PER_DAY", "10"),
                field_name="TRADINGAGENTS_MAX_REVIEWS_PER_DAY",
            ),
            output_language=_clean_optional(env.get("TRADINGAGENTS_OUTPUT_LANGUAGE")) or "English",
            backend_url=_clean_optional(env.get("TRADINGAGENTS_BACKEND_URL")),
            tradingagents_repo_path=_optional_path(env.get("TRADINGAGENTS_REPO_PATH"))
            or _default_tradingagents_repo_path(),
            results_dir=_optional_path(env.get("TRADINGAGENTS_RESULTS_DIR")) or storage_dir / "results",
            data_cache_dir=_optional_path(env.get("TRADINGAGENTS_CACHE_DIR")) or storage_dir / "cache",
            memory_log_path=(
                _optional_path(env.get("TRADINGAGENTS_MEMORY_LOG_PATH"))
                or storage_dir / "memory" / "trading_memory.md"
            ),
        )

    def ensure_storage_paths(self) -> None:
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.data_cache_dir.mkdir(parents=True, exist_ok=True)
        self.memory_log_path.parent.mkdir(parents=True, exist_ok=True)

    def to_tradingagents_config(self, default_config: Mapping[str, Any]) -> dict[str, Any]:
        config = dict(default_config)
        config.update(
            {
                "llm_provider": self.llm_provider,
                "deep_think_llm": self.deep_model,
                "quick_think_llm": self.quick_model,
                "max_debate_rounds": self.max_debate_rounds,
                "max_risk_discuss_rounds": self.max_risk_discuss_rounds,
                "max_recur_limit": self.max_recur_limit,
                "output_language": self.output_language,
                "checkpoint_enabled": False,
                "data_vendors": dict(self.data_vendors),
                "results_dir": str(self.results_dir),
                "data_cache_dir": str(self.data_cache_dir),
                "memory_log_path": str(self.memory_log_path),
            }
        )
        if self.backend_url is not None:
            config["backend_url"] = self.backend_url
        return config


@dataclass(frozen=True, slots=True)
class TradingAgentsReviewResult:
    ticker: str
    trade_date: str
    status: str
    decision: Any | None
    llm_provider: str
    deep_model: str
    quick_model: str
    cached: bool = False
    error: str | None = None
    duration_seconds: float = 0.0
    reviewed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "date": self.trade_date,
            "status": self.status,
            "decision": self.decision,
            "llm_provider": self.llm_provider,
            "deep_model": self.deep_model,
            "quick_model": self.quick_model,
            "cached": self.cached,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
            "reviewed_at": self.reviewed_at.isoformat(),
        }


class TradingAgentsReviewer:
    """Runs TradingAgents only for already-qualified scanner setups."""

    def __init__(
        self,
        config: TradingAgentsReviewConfig | None = None,
        *,
        debug: bool = False,
        agent_factory: AgentFactory | None = None,
        default_config: Mapping[str, Any] | None = None,
    ) -> None:
        self.config = config or TradingAgentsReviewConfig()
        self.debug = debug
        self._agent_factory = agent_factory
        self._default_config = default_config
        self._agent: Any | None = None
        self._cache: dict[tuple[str, str], TradingAgentsReviewResult] = {}
        self._review_count_date = date.today()
        self._review_count = 0

    def review(
        self,
        ticker: str,
        trade_date: str | None = None,
        *,
        force: bool = False,
    ) -> TradingAgentsReviewResult:
        normalized_ticker = _normalize_ticker(ticker)
        review_date = trade_date or date.today().isoformat()
        cache_key = (normalized_ticker, review_date)

        if not force and cache_key in self._cache:
            cached = self._cache[cache_key]
            return TradingAgentsReviewResult(
                ticker=cached.ticker,
                trade_date=cached.trade_date,
                status=cached.status,
                decision=cached.decision,
                llm_provider=cached.llm_provider,
                deep_model=cached.deep_model,
                quick_model=cached.quick_model,
                cached=True,
                error=cached.error,
                duration_seconds=0.0,
            )

        if self._daily_cap_reached():
            return self._result(
                normalized_ticker,
                review_date,
                status="skipped",
                decision=None,
                error="daily TradingAgents review cap reached",
            )

        missing_key_error = self._missing_provider_key_error()
        if missing_key_error is not None:
            return self._result(
                normalized_ticker,
                review_date,
                status="error",
                decision=None,
                error=missing_key_error,
            )

        start = time.perf_counter()
        try:
            agent = self._get_agent()
            self._increment_daily_count()
            _, decision = agent.propagate(normalized_ticker, review_date)
        except TradingAgentsUnavailableError as exc:
            return self._result(
                normalized_ticker,
                review_date,
                status="error",
                decision=None,
                error=str(exc),
                duration_seconds=time.perf_counter() - start,
            )
        except Exception as exc:
            logger.exception("TradingAgents review failed for %s on %s", normalized_ticker, review_date)
            return self._result(
                normalized_ticker,
                review_date,
                status="error",
                decision=None,
                error=str(exc),
                duration_seconds=time.perf_counter() - start,
            )

        result = self._result(
            normalized_ticker,
            review_date,
            status="ok",
            decision=decision,
            duration_seconds=time.perf_counter() - start,
        )
        self._cache[cache_key] = result
        return result

    def clear_cache(self) -> None:
        self._cache.clear()

    def _result(
        self,
        ticker: str,
        trade_date: str,
        *,
        status: str,
        decision: Any | None,
        error: str | None = None,
        duration_seconds: float = 0.0,
    ) -> TradingAgentsReviewResult:
        return TradingAgentsReviewResult(
            ticker=ticker,
            trade_date=trade_date,
            status=status,
            decision=decision,
            llm_provider=self.config.llm_provider,
            deep_model=self.config.deep_model,
            quick_model=self.config.quick_model,
            error=error,
            duration_seconds=duration_seconds,
        )

    def _get_agent(self) -> Any:
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent

    def _build_agent(self) -> Any:
        self.config.ensure_storage_paths()
        default_config = self._resolve_default_config()
        tradingagents_config = self.config.to_tradingagents_config(default_config)

        if self._agent_factory is not None:
            return self._agent_factory(tradingagents_config, self.debug)

        try:
            from tradingagents.graph.trading_graph import TradingAgentsGraph
        except ImportError as exc:
            raise TradingAgentsUnavailableError(
                "TradingAgents is not installed. Install it separately or set TRADINGAGENTS_REPO_PATH."
            ) from exc

        return TradingAgentsGraph(debug=self.debug, config=tradingagents_config)

    def _resolve_default_config(self) -> Mapping[str, Any]:
        if self._default_config is not None:
            return self._default_config

        if self._agent_factory is not None:
            return {}

        if self.config.tradingagents_repo_path is not None:
            repo_path = str(self.config.tradingagents_repo_path)
            if repo_path not in sys.path:
                sys.path.insert(0, repo_path)

        try:
            from tradingagents.default_config import DEFAULT_CONFIG
        except ImportError as exc:
            raise TradingAgentsUnavailableError(
                "TradingAgents default config is not importable. Install the package or set TRADINGAGENTS_REPO_PATH."
            ) from exc
        return DEFAULT_CONFIG

    def _daily_cap_reached(self) -> bool:
        self._reset_daily_count_if_needed()
        return self._review_count >= self.config.max_reviews_per_day

    def _increment_daily_count(self) -> None:
        self._reset_daily_count_if_needed()
        self._review_count += 1

    def _reset_daily_count_if_needed(self) -> None:
        today = date.today()
        if self._review_count_date != today:
            self._review_count_date = today
            self._review_count = 0

    def _missing_provider_key_error(self) -> str | None:
        if self._agent_factory is not None:
            return None
        provider = self.config.llm_provider.strip().lower()
        required_names = _PROVIDER_KEY_ENV_VARS.get(provider)
        if required_names is None:
            return None
        if any(_clean_optional(os.getenv(name)) is not None for name in required_names):
            return None
        joined = " or ".join(required_names)
        return f"missing {joined} for TradingAgents provider '{provider}'"
