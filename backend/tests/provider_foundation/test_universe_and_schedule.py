from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.runtime.session_window import RuntimeWindow, SessionPhase


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
