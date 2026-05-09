from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Mapping


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _required_positive_float(value: str, *, field_name: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return parsed


def _required_non_negative_int(value: str, *, field_name: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{field_name} must be zero or greater")
    return parsed


def _env_flag(value: str | None, *, default: bool = False) -> bool:
    cleaned = _clean_optional(value)
    if cleaned is None:
        return default
    return cleaned.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class ProviderEndpointConfig:
    base_url: str
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        normalized_base_url = self.base_url.rstrip("/")
        if not normalized_base_url:
            raise ValueError("base_url must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        object.__setattr__(self, "base_url", normalized_base_url)


@dataclass(frozen=True, slots=True)
class PolygonConfig:
    api_key: str | None
    endpoint: ProviderEndpointConfig

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "PolygonConfig":
        return cls(
            api_key=_clean_optional(env.get("POLYGON_API_KEY")),
            endpoint=ProviderEndpointConfig(
                base_url=env.get("POLYGON_BASE_URL", "https://api.polygon.io"),
                timeout_seconds=_required_positive_float(
                    env.get("POLYGON_TIMEOUT_SECONDS", "10"),
                    field_name="POLYGON_TIMEOUT_SECONDS",
                ),
            ),
        )


@dataclass(frozen=True, slots=True)
class BenzingaConfig:
    api_key: str | None
    endpoint: ProviderEndpointConfig

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "BenzingaConfig":
        return cls(
            api_key=_clean_optional(env.get("BENZINGA_API_KEY")),
            endpoint=ProviderEndpointConfig(
                base_url=env.get("BENZINGA_BASE_URL", "https://api.benzinga.com"),
                timeout_seconds=_required_positive_float(
                    env.get("BENZINGA_TIMEOUT_SECONDS", "10"),
                    field_name="BENZINGA_TIMEOUT_SECONDS",
                ),
            ),
        )


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    bot_token: str | None
    operator_chat_id: str | None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "TelegramConfig":
        return cls(
            bot_token=_clean_optional(env.get("TELEGRAM_BOT_TOKEN")),
            operator_chat_id=_clean_optional(env.get("TELEGRAM_OPERATOR_CHAT_ID")),
        )

    @property
    def is_configured(self) -> bool:
        return self.bot_token is not None and self.operator_chat_id is not None


@dataclass(frozen=True, slots=True)
class LLMConfig:
    api_key: str | None
    base_url: str
    model: str
    temperature: float

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "LLMConfig":
        # Support Groq (preferred, free) or OpenAI (legacy)
        groq_key = _clean_optional(env.get("GROQ_API_KEY"))
        openai_key = _clean_optional(env.get("OPENAI_API_KEY"))

        if groq_key:
            return cls(
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1",
                model=env.get("LLM_MODEL", "llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile",
                temperature=float(env.get("LLM_TEMPERATURE", "0.1")),
            )
        else:
            return cls(
                api_key=openai_key,
                base_url="https://api.openai.com/v1",
                model=env.get("OPENAI_MODEL", env.get("LLM_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini",
                temperature=float(env.get("OPENAI_TEMPERATURE", env.get("LLM_TEMPERATURE", "0.1"))),
            )

    @property
    def is_configured(self) -> bool:
        return self.api_key is not None


@dataclass(frozen=True, slots=True)
class AgentReviewRuntimeConfig:
    enabled: bool
    min_score: int
    timeout_seconds: float

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AgentReviewRuntimeConfig":
        return cls(
            enabled=_env_flag(env.get("TRADINGAGENTS_REVIEW_ENABLED"), default=False),
            min_score=_required_non_negative_int(
                env.get("TRADINGAGENTS_REVIEW_MIN_SCORE", "0"),
                field_name="TRADINGAGENTS_REVIEW_MIN_SCORE",
            ),
            timeout_seconds=_required_positive_float(
                env.get("TRADINGAGENTS_REVIEW_TIMEOUT_SECONDS", "180"),
                field_name="TRADINGAGENTS_REVIEW_TIMEOUT_SECONDS",
            ),
        )


@dataclass(frozen=True, slots=True)
class AppConfig:
    polygon: PolygonConfig
    benzinga: BenzingaConfig
    telegram: TelegramConfig
    llm: LLMConfig
    agent_review: AgentReviewRuntimeConfig
    dashboard_password: str | None
    dashboard_session_secret: str | None
    dashboard_session_cookie_name: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AppConfig":
        source = environ if env is None else env
        return cls(
            polygon=PolygonConfig.from_env(source),
            benzinga=BenzingaConfig.from_env(source),
            telegram=TelegramConfig.from_env(source),
            llm=LLMConfig.from_env(source),
            agent_review=AgentReviewRuntimeConfig.from_env(source),
            dashboard_password=_clean_optional(source.get("DASHBOARD_PASSWORD")),
            dashboard_session_secret=_clean_optional(source.get("DASHBOARD_SESSION_SECRET")),
            dashboard_session_cookie_name=source.get(
                "DASHBOARD_SESSION_COOKIE_NAME",
                "buy_signal_dashboard_session",
            ).strip()
            or "buy_signal_dashboard_session",
        )
