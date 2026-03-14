from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from re import sub
from typing import Any

from app.config import BenzingaConfig

from .base import JsonFetcher, NewsProvider, normalize_symbols, utc_now
from .errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderPayloadError,
    ProviderRateLimitError,
    ProviderTransportError,
    ProviderUnavailableError,
)
from .models import (
    CatalystTag,
    NewsEvent,
    ProviderBatch,
    ProviderCapability,
    ProviderHealthSnapshot,
    ProviderHealthState,
)


def _parse_benzinga_datetime(value: Any, *, field_name: str) -> datetime:
    if value is None:
        raise ProviderPayloadError("benzinga", f"missing {field_name}")
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = parsedate_to_datetime(str(value))
        except (TypeError, ValueError) as exc:
            raise ProviderPayloadError("benzinga", f"invalid {field_name}: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProviderPayloadError("benzinga", f"{field_name} must be timezone-aware")
    return parsed.astimezone(UTC)


def _strip_html(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = sub(r"<[^>]+>", " ", value)
    normalized = " ".join(unescape(cleaned).split())
    return normalized or None


def _classify_catalyst(channels: Sequence[str], headline: str) -> CatalystTag:
    haystack = " ".join([headline, *channels]).lower()
    if "earnings" in haystack:
        return CatalystTag.EARNINGS
    if "guidance" in haystack:
        return CatalystTag.GUIDANCE
    if "offering" in haystack:
        return CatalystTag.OFFERING
    if "fda" in haystack:
        return CatalystTag.FDA
    if any(term in haystack for term in ("merger", "acquisition", "m&a")):
        return CatalystTag.M_AND_A
    if "analyst" in haystack or "upgrade" in haystack or "downgrade" in haystack:
        return CatalystTag.ANALYST
    if "breaking" in haystack:
        return CatalystTag.BREAKING_NEWS
    if haystack.strip():
        return CatalystTag.GENERAL
    return CatalystTag.UNKNOWN


def _translate_benzinga_error(payload: Mapping[str, Any]) -> None:
    raw_message = str(
        payload.get("error")
        or payload.get("message")
        or payload.get("status")
        or "benzinga request failed"
    )
    message = raw_message.lower()
    if "auth" in message or "token" in message or "api key" in message:
        raise ProviderAuthenticationError("benzinga", raw_message)
    if "rate" in message or "limit" in message:
        raise ProviderRateLimitError("benzinga", raw_message)
    if "unavailable" in message or "down" in message:
        raise ProviderUnavailableError("benzinga", raw_message)
    raise ProviderPayloadError("benzinga", raw_message)


class BenzingaNewsProvider(NewsProvider):
    provider_name = "benzinga"

    def __init__(
        self,
        config: BenzingaConfig,
        *,
        fetch_json: JsonFetcher,
        now_fn: Callable[[], datetime] = utc_now,
    ) -> None:
        self._config = config
        self._fetch_json = fetch_json
        self._now_fn = now_fn

    async def fetch_recent_news(
        self,
        symbols: Sequence[str],
        *,
        updated_since: datetime | None = None,
        limit: int = 100,
    ) -> ProviderBatch[NewsEvent]:
        normalized_symbols = normalize_symbols(symbols)
        if not normalized_symbols:
            raise ValueError("at least one symbol is required")
        if not self._config.api_key:
            raise ProviderConfigurationError("benzinga", "BENZINGA_API_KEY is not configured")

        params: dict[str, Any] = {
            "token": self._config.api_key,
            "tickers": ",".join(normalized_symbols),
            "pageSize": limit,
        }
        if updated_since is not None:
            params["updatedSince"] = updated_since.astimezone(UTC).isoformat()

        try:
            payload = await self._fetch_json(
                f"{self._config.endpoint.base_url}/api/v2/news",
                params,
            )
        except ProviderTransportError:
            raise
        except TimeoutError as exc:
            raise ProviderTransportError("benzinga", "benzinga request timed out") from exc
        except Exception as exc:  # pragma: no cover - defensive adapter boundary
            raise ProviderTransportError("benzinga", f"benzinga transport error: {exc}") from exc

        received_at = self._now_fn()
        return self._normalize_batch(payload, received_at=received_at)

    def _normalize_batch(
        self,
        payload: Any,
        *,
        received_at: datetime,
    ) -> ProviderBatch[NewsEvent]:
        if isinstance(payload, Mapping):
            _translate_benzinga_error(payload)
        if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
            raise ProviderPayloadError("benzinga", "expected list payload")

        events = tuple(self._normalize_event(raw_item, received_at=received_at) for raw_item in payload)
        last_update_at = max(
            (event.updated_at or event.published_at for event in events),
            default=None,
        )
        freshness_age = (
            max((received_at - last_update_at).total_seconds(), 0.0)
            if last_update_at is not None
            else None
        )
        health = ProviderHealthSnapshot(
            provider=self.provider_name,
            capability=ProviderCapability.NEWS,
            observed_at=received_at,
            last_update_at=last_update_at,
            freshness_age_seconds=freshness_age,
            state=ProviderHealthState.HEALTHY,
            reason="normalized_news_batch",
        )
        return ProviderBatch(
            provider=self.provider_name,
            capability=ProviderCapability.NEWS,
            fetched_at=received_at,
            records=events,
            health=health,
        )

    def _normalize_event(
        self,
        raw_item: Any,
        *,
        received_at: datetime,
    ) -> NewsEvent:
        if not isinstance(raw_item, Mapping):
            raise ProviderPayloadError("benzinga", "news item must be a mapping")

        channels = tuple(
            str(channel.get("name", "")).strip()
            for channel in raw_item.get("channels", [])
            if isinstance(channel, Mapping) and str(channel.get("name", "")).strip()
        )
        stocks = tuple(
            str(stock.get("name", "")).strip()
            for stock in raw_item.get("stocks", [])
            if isinstance(stock, Mapping) and str(stock.get("name", "")).strip()
        )
        headline = str(raw_item.get("title", "")).strip()
        return NewsEvent(
            event_id=str(raw_item.get("id", "")).strip(),
            provider=self.provider_name,
            published_at=_parse_benzinga_datetime(raw_item.get("created"), field_name="created"),
            received_at=received_at,
            updated_at=(
                _parse_benzinga_datetime(raw_item.get("updated"), field_name="updated")
                if raw_item.get("updated")
                else None
            ),
            headline=headline,
            summary=_strip_html(raw_item.get("body")),
            symbols=stocks,
            channels=channels,
            authors=(str(raw_item.get("author", "")).strip(),) if str(raw_item.get("author", "")).strip() else (),
            url=str(raw_item.get("url", "")).strip() or None,
            catalyst_tag=_classify_catalyst(channels, headline),
            is_correction=any("correction" in channel.lower() for channel in channels),
        )
