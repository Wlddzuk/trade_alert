from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.ops.alert_delivery_health import (
    AlertDeliveryAttempt,
    AlertDeliveryHealthService,
    AlertDeliveryResult,
    build_alert_delivery_snapshot,
)
from app.ops.incident_log import IncidentLogService


def test_runtime_delivery_snapshot_tracks_failure_streak_and_last_success() -> None:
    observed_at = datetime(2026, 3, 18, 15, 0, tzinfo=UTC)
    attempts = (
        AlertDeliveryAttempt(
            occurred_at=observed_at - timedelta(minutes=4),
            symbol="AKRX",
            alert_id="akrx-actionable-1",
            result=AlertDeliveryResult.SUCCESS,
            reason="delivered",
        ),
        AlertDeliveryAttempt(
            occurred_at=observed_at - timedelta(minutes=2),
            symbol="AKRX",
            alert_id="akrx-actionable-1",
            result=AlertDeliveryResult.FAILURE,
            reason="telegram_timeout",
        ),
        AlertDeliveryAttempt(
            occurred_at=observed_at - timedelta(minutes=1),
            symbol="AKRX",
            alert_id="akrx-actionable-1",
            result=AlertDeliveryResult.FAILURE,
            reason="telegram_rate_limited",
        ),
    )

    snapshot = build_alert_delivery_snapshot(attempts, observed_at=observed_at)
    report = AlertDeliveryHealthService().build_report(attempts, observed_at=observed_at)

    assert snapshot.consecutive_failures == 2
    assert snapshot.last_success_at == observed_at - timedelta(minutes=4)
    assert snapshot.last_failure_reason == "telegram_rate_limited"
    assert report.snapshot.summary == "Alert delivery failures detected."
    assert report.recent_failures[0].consecutive_failures == 2
    assert report.recent_failures[0].last_success_at == observed_at - timedelta(minutes=4)


def test_runtime_delivery_failures_surface_as_incidents() -> None:
    observed_at = datetime(2026, 3, 18, 15, 15, tzinfo=UTC)
    report = AlertDeliveryHealthService().build_report(
        (
            AlertDeliveryAttempt(
                occurred_at=observed_at - timedelta(minutes=1),
                symbol="BMEA",
                alert_id="bmea-actionable-1",
                result=AlertDeliveryResult.FAILURE,
                reason="telegram_timeout",
            ),
        ),
        observed_at=observed_at,
    )

    incident_report = IncidentLogService().build((), delivery_report=report)

    assert incident_report.recent_critical_issues[0].title == "Alert delivery failure"
    assert incident_report.recent_critical_issues[0].summary == "telegram_timeout"
    assert incident_report.recent_critical_issues[0].source == "alert_delivery"
