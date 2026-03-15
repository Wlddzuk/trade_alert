from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import PolygonConfig

from .base import JsonFetcher, MarketDataProvider, normalize_symbols, utc_now
from .errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderPayloadError,
    ProviderRateLimitError,
    ProviderTransportError,
    ProviderUnavailableError,
)
from .models import (
    DailyBar,
    IntradayBar,
    MarketSnapshot,
    ProviderBatch,
    ProviderCapability,
    ProviderHealthSnapshot,
    ProviderHealthState,
)


def _datetime_from_epoch_ms(value: Any, *, field_name: str) -> datetime:
    if value is None:
        raise ProviderPayloadError("polygon", f"missing {field_name}")
    try:
        timestamp = float(value) / 1000
    except (TypeError, ValueError) as exc:
        raise ProviderPayloadError("polygon", f"invalid {field_name}: {value!r}") from exc
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _translate_polygon_error(payload: Mapping[str, Any]) -> None:
    raw_message = str(
        payload.get("error")
        or payload.get("message")
        or payload.get("status")
        or "polygon request failed"
    )
    message = raw_message.lower()
    if "auth" in message or "api key" in message:
        raise ProviderAuthenticationError("polygon", raw_message)
    if "rate" in message or "limit" in message:
        raise ProviderRateLimitError("polygon", raw_message)
    if "unavailable" in message or "down" in message:
        raise ProviderUnavailableError("polygon", raw_message)
    raise ProviderPayloadError("polygon", raw_message)


class PolygonSnapshotProvider(MarketDataProvider):
    provider_name = "polygon"

    def __init__(
        self,
        config: PolygonConfig,
        *,
        fetch_json: JsonFetcher,
        now_fn: Callable[[], datetime] = utc_now,
    ) -> None:
        self._config = config
        self._fetch_json = fetch_json
        self._now_fn = now_fn

    async def fetch_market_snapshots(
        self,
        symbols: Sequence[str],
    ) -> ProviderBatch[MarketSnapshot]:
        normalized_symbols = normalize_symbols(symbols)
        if not normalized_symbols:
            raise ValueError("at least one symbol is required")
        if not self._config.api_key:
            raise ProviderConfigurationError("polygon", "POLYGON_API_KEY is not configured")

        try:
            payload = await self._fetch_json(
                f"{self._config.endpoint.base_url}/v2/snapshot/locale/us/markets/stocks/tickers",
                {
                    "ticker.any_of": ",".join(normalized_symbols),
                    "apiKey": self._config.api_key,
                },
            )
        except ProviderTransportError:
            raise
        except TimeoutError as exc:
            raise ProviderTransportError("polygon", "polygon request timed out") from exc
        except Exception as exc:  # pragma: no cover - defensive adapter boundary
            raise ProviderTransportError("polygon", f"polygon transport error: {exc}") from exc

        received_at = self._now_fn()
        return self._normalize_batch(payload, received_at=received_at)

    async def fetch_daily_bars(
        self,
        symbols: Sequence[str],
        *,
        lookback_days: int = 20,
    ) -> ProviderBatch[DailyBar]:
        if lookback_days <= 0:
            raise ValueError("lookback_days must be greater than zero")

        normalized_symbols = normalize_symbols(symbols)
        if not normalized_symbols:
            raise ValueError("at least one symbol is required")
        if not self._config.api_key:
            raise ProviderConfigurationError("polygon", "POLYGON_API_KEY is not configured")

        received_at = self._now_fn()
        start_date = (received_at - timedelta(days=lookback_days * 2)).date().isoformat()
        end_date = received_at.date().isoformat()
        bars = await self._fetch_aggregate_history(
            normalized_symbols,
            received_at=received_at,
            start_date=start_date,
            end_date=end_date,
            path_template="/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}",
            params={"adjusted": "true", "sort": "asc", "limit": lookback_days},
            normalizer=self._normalize_daily_bar,
        )
        return self._history_batch(
            records=bars,
            received_at=received_at,
        )

    async def fetch_intraday_bars(
        self,
        symbols: Sequence[str],
        *,
        interval_minutes: int | None = 5,
        interval_seconds: int | None = None,
        lookback_days: int = 20,
    ) -> ProviderBatch[IntradayBar]:
        if lookback_days <= 0:
            raise ValueError("lookback_days must be greater than zero")
        if (interval_minutes is None) == (interval_seconds is None):
            raise ValueError("exactly one of interval_minutes or interval_seconds must be provided")
        if interval_minutes is not None and interval_minutes <= 0:
            raise ValueError("interval_minutes must be greater than zero")
        if interval_seconds is not None and interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")

        normalized_symbols = normalize_symbols(symbols)
        if not normalized_symbols:
            raise ValueError("at least one symbol is required")
        if not self._config.api_key:
            raise ProviderConfigurationError("polygon", "POLYGON_API_KEY is not configured")

        received_at = self._now_fn()
        start_date = (received_at - timedelta(days=lookback_days * 2)).date().isoformat()
        end_date = received_at.date().isoformat()
        interval_value = interval_seconds or interval_minutes or 0
        interval_unit = "second" if interval_seconds is not None else "minute"
        bars_per_day = 1_560 if interval_unit == "second" else 78
        bars = await self._fetch_aggregate_history(
            normalized_symbols,
            received_at=received_at,
            start_date=start_date,
            end_date=end_date,
            path_template=f"/v2/aggs/ticker/{{symbol}}/range/{interval_value}/{interval_unit}/{{start}}/{{end}}",
            params={"adjusted": "true", "sort": "asc", "limit": lookback_days * bars_per_day},
            normalizer=lambda symbol, raw_item: self._normalize_intraday_bar(
                symbol,
                raw_item,
                interval_minutes=interval_minutes,
                interval_seconds=interval_seconds,
            ),
        )
        return self._history_batch(
            records=bars,
            received_at=received_at,
        )

    def _normalize_batch(
        self,
        payload: Any,
        *,
        received_at: datetime,
    ) -> ProviderBatch[MarketSnapshot]:
        if not isinstance(payload, Mapping):
            raise ProviderPayloadError("polygon", "expected mapping payload")

        status = str(payload.get("status", "")).upper()
        if status and status != "OK":
            _translate_polygon_error(payload)

        raw_tickers = payload.get("tickers", [])
        if not isinstance(raw_tickers, Sequence):
            raise ProviderPayloadError("polygon", "expected tickers list")

        snapshots = tuple(self._normalize_snapshot(raw_item, received_at=received_at) for raw_item in raw_tickers)
        last_update_at = max((snapshot.observed_at for snapshot in snapshots), default=None)
        freshness_age = (
            max((received_at - last_update_at).total_seconds(), 0.0)
            if last_update_at is not None
            else None
        )
        health = ProviderHealthSnapshot(
            provider=self.provider_name,
            capability=ProviderCapability.MARKET_DATA,
            observed_at=received_at,
            last_update_at=last_update_at,
            freshness_age_seconds=freshness_age,
            state=ProviderHealthState.HEALTHY,
            reason="normalized_market_snapshot_batch",
        )
        return ProviderBatch(
            provider=self.provider_name,
            capability=ProviderCapability.MARKET_DATA,
            fetched_at=received_at,
            records=snapshots,
            health=health,
        )

    async def _fetch_aggregate_history(
        self,
        symbols: Sequence[str],
        *,
        received_at: datetime,
        start_date: str,
        end_date: str,
        path_template: str,
        params: Mapping[str, Any],
        normalizer: Callable[[str, Any], DailyBar | IntradayBar],
    ) -> tuple[DailyBar | IntradayBar, ...]:
        bars: list[DailyBar | IntradayBar] = []

        for symbol in symbols:
            try:
                payload = await self._fetch_json(
                    f"{self._config.endpoint.base_url}{path_template.format(symbol=symbol, start=start_date, end=end_date)}",
                    {"apiKey": self._config.api_key, **params},
                )
            except ProviderTransportError:
                raise
            except TimeoutError as exc:
                raise ProviderTransportError("polygon", "polygon request timed out") from exc
            except Exception as exc:  # pragma: no cover - defensive adapter boundary
                raise ProviderTransportError("polygon", f"polygon transport error: {exc}") from exc

            bars.extend(self._normalize_aggregate_payload(symbol, payload, normalizer=normalizer))

        return tuple(bars)

    def _normalize_aggregate_payload(
        self,
        symbol: str,
        payload: Any,
        *,
        normalizer: Callable[[str, Any], DailyBar | IntradayBar],
    ) -> tuple[DailyBar | IntradayBar, ...]:
        if not isinstance(payload, Mapping):
            raise ProviderPayloadError("polygon", "expected mapping payload")

        status = str(payload.get("status", "")).upper()
        if status and status != "OK":
            _translate_polygon_error(payload)

        raw_results = payload.get("results", [])
        if not isinstance(raw_results, Sequence):
            raise ProviderPayloadError("polygon", "expected aggregate results list")

        return tuple(normalizer(symbol, raw_item) for raw_item in raw_results)

    def _history_batch(
        self,
        *,
        records: tuple[DailyBar | IntradayBar, ...],
        received_at: datetime,
    ) -> ProviderBatch[DailyBar | IntradayBar]:
        last_update_at = max(
            (
                record.observed_at if isinstance(record, DailyBar) else record.start_at
                for record in records
            ),
            default=None,
        )
        freshness_age = (
            max((received_at - last_update_at).total_seconds(), 0.0)
            if last_update_at is not None
            else None
        )
        health = ProviderHealthSnapshot(
            provider=self.provider_name,
            capability=ProviderCapability.MARKET_DATA,
            observed_at=received_at,
            last_update_at=last_update_at,
            freshness_age_seconds=freshness_age,
            state=ProviderHealthState.HEALTHY,
            reason="normalized_market_history_batch",
        )
        return ProviderBatch(
            provider=self.provider_name,
            capability=ProviderCapability.MARKET_DATA,
            fetched_at=received_at,
            records=records,
            health=health,
        )

    def _normalize_snapshot(
        self,
        raw_item: Any,
        *,
        received_at: datetime,
    ) -> MarketSnapshot:
        if not isinstance(raw_item, Mapping):
            raise ProviderPayloadError("polygon", "snapshot item must be a mapping")

        day = raw_item.get("day", {})
        prev_day = raw_item.get("prevDay", {})
        last_trade = raw_item.get("lastTrade", {})
        if not isinstance(day, Mapping) or not isinstance(prev_day, Mapping) or not isinstance(last_trade, Mapping):
            raise ProviderPayloadError("polygon", "invalid polygon snapshot sections")

        observed_at = _datetime_from_epoch_ms(
            last_trade.get("t") or raw_item.get("updated"),
            field_name="last trade timestamp",
        )
        return MarketSnapshot(
            symbol=str(raw_item.get("ticker", "")),
            provider=self.provider_name,
            observed_at=observed_at,
            received_at=received_at,
            last_price=last_trade.get("p"),
            session_volume=int(day.get("v", 0)),
            previous_close=prev_day.get("c"),
            open_price=day.get("o"),
            high_price=day.get("h"),
            low_price=day.get("l"),
            vwap=day.get("vw"),
            exchange=raw_item.get("primary_exchange"),
        )

    def _normalize_daily_bar(self, symbol: str, raw_item: Any) -> DailyBar:
        if not isinstance(raw_item, Mapping):
            raise ProviderPayloadError("polygon", "daily bar item must be a mapping")

        observed_at = _datetime_from_epoch_ms(raw_item.get("t"), field_name="daily bar timestamp")
        return DailyBar(
            symbol=symbol,
            provider=self.provider_name,
            trading_date=observed_at.date(),
            observed_at=observed_at,
            open_price=raw_item.get("o"),
            high_price=raw_item.get("h"),
            low_price=raw_item.get("l"),
            close_price=raw_item.get("c"),
            volume=int(raw_item.get("v", 0)),
        )

    def _normalize_intraday_bar(
        self,
        symbol: str,
        raw_item: Any,
        *,
        interval_minutes: int | None = None,
        interval_seconds: int | None = None,
    ) -> IntradayBar:
        if not isinstance(raw_item, Mapping):
            raise ProviderPayloadError("polygon", "intraday bar item must be a mapping")

        return IntradayBar(
            symbol=symbol,
            provider=self.provider_name,
            start_at=_datetime_from_epoch_ms(raw_item.get("t"), field_name="intraday bar timestamp"),
            interval_minutes=interval_minutes,
            interval_seconds=interval_seconds,
            open_price=raw_item.get("o"),
            high_price=raw_item.get("h"),
            low_price=raw_item.get("l"),
            close_price=raw_item.get("c"),
            volume=int(raw_item.get("v", 0)),
        )
