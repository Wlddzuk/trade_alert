from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.providers.models import InstrumentRecord, SecurityType
from app.runtime.session_window import RuntimeWindow, SessionPhase
from app.universe.filters import UniverseFilter
from app.universe.models import EligibilityReason, UniverseCandidate
from app.universe.reference_data import UniverseReferenceData


@pytest.fixture
def runtime_window() -> RuntimeWindow:
    return RuntimeWindow()


def test_runtime_window_identifies_session_phases(runtime_window: RuntimeWindow) -> None:
    assert runtime_window.phase_at(datetime(2026, 3, 13, 7, 59, tzinfo=UTC)) is SessionPhase.OFFLINE
    assert runtime_window.phase_at(datetime(2026, 3, 13, 8, 0, tzinfo=UTC)) is SessionPhase.PREMARKET
    assert runtime_window.phase_at(datetime(2026, 3, 13, 13, 30, tzinfo=UTC)) is SessionPhase.REGULAR
    assert runtime_window.phase_at(datetime(2026, 3, 13, 20, 15, tzinfo=UTC)) is SessionPhase.POST_CLOSE
    assert runtime_window.phase_at(datetime(2026, 3, 13, 20, 31, tzinfo=UTC)) is SessionPhase.OFFLINE


def test_runtime_window_status_reports_utc_and_et(runtime_window: RuntimeWindow) -> None:
    status = runtime_window.status_at(datetime(2026, 3, 13, 13, 45, tzinfo=UTC))

    assert status.observed_at_utc == datetime(2026, 3, 13, 13, 45, tzinfo=UTC)
    assert status.observed_at_et.hour == 9
    assert status.observed_at_et.minute == 45
    assert status.phase is SessionPhase.REGULAR
    assert status.scanning_active is True


def test_runtime_window_rejects_naive_datetimes(runtime_window: RuntimeWindow) -> None:
    with pytest.raises(ValueError, match="observed_at must be timezone-aware"):
        runtime_window.phase_at(datetime(2026, 3, 13, 13, 45))


def test_universe_filter_accepts_valid_common_stock() -> None:
    candidate = UniverseCandidate.from_instrument_record(
        InstrumentRecord(
            symbol="acme",
            exchange="nasdaq",
            security_type=SecurityType.COMMON_STOCK,
            is_common_stock=True,
            average_daily_volume=900_000,
            updated_at=datetime(2026, 3, 13, 12, 0, tzinfo=UTC),
        ),
        last_price="7.25",
    )

    decision = UniverseFilter().evaluate(candidate)

    assert decision.eligible is True
    assert decision.reasons == ()


def test_universe_filter_fails_closed_on_missing_metadata() -> None:
    candidate = UniverseCandidate(
        symbol="acme",
        exchange=None,
        is_common_stock=None,
        instrument_type=None,
        last_price="7.25",
        average_daily_volume=None,
    )

    decision = UniverseFilter().evaluate(candidate)

    assert decision.eligible is False
    assert EligibilityReason.MISSING_METADATA in decision.reasons
    assert EligibilityReason.EXCHANGE_NOT_ALLOWED in decision.reasons
    assert EligibilityReason.NOT_COMMON_STOCK in decision.reasons
    assert EligibilityReason.ADV_BELOW_MINIMUM in decision.reasons


def test_universe_filter_rejects_excluded_types_and_hard_filter_failures() -> None:
    candidate = UniverseCandidate(
        symbol="fund",
        exchange="NASDAQ",
        is_common_stock=False,
        instrument_type="etf",
        last_price="35.00",
        average_daily_volume=100_000,
    )

    decision = UniverseFilter().evaluate(candidate)

    assert decision.eligible is False
    assert EligibilityReason.EXCLUDED_INSTRUMENT_TYPE in decision.reasons
    assert EligibilityReason.PRICE_OUTSIDE_RANGE in decision.reasons
    assert EligibilityReason.ADV_BELOW_MINIMUM in decision.reasons


def test_reference_data_returns_only_eligible_candidates() -> None:
    reference_data = UniverseReferenceData(
        [
            UniverseCandidate(
                symbol="acme",
                exchange="NASDAQ",
                is_common_stock=True,
                instrument_type="common_stock",
                last_price="6.50",
                average_daily_volume=750_000,
            ),
            UniverseCandidate(
                symbol="otcy",
                exchange="OTC",
                is_common_stock=True,
                instrument_type="otc",
                last_price="4.00",
                average_daily_volume=900_000,
            ),
        ]
    )

    eligible = reference_data.eligible_candidates(UniverseFilter())

    assert [candidate.symbol for candidate in eligible] == ["ACME"]
