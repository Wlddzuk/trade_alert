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
class AppConfig:
    polygon: PolygonConfig
    benzinga: BenzingaConfig

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AppConfig":
        source = environ if env is None else env
        return cls(
            polygon=PolygonConfig.from_env(source),
            benzinga=BenzingaConfig.from_env(source),
        )
