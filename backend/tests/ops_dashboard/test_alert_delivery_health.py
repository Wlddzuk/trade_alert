from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.ops.alert_delivery_health import AlertDeliveryFailure
from app.ops.overview_service import OperationsOverviewService


def test_alert_failure_log_keeps_recent_delivery_failures_separate_from_current_health() -> None:
    observed_at = datetime(2026, 3, 17, 14, 10, tzinfo=UTC)
    service = OperationsOverviewService()

    report = service.build_alert_failure_log(
        (
            AlertDeliveryFailure(
                observed_at=observed_at - timedelta(minutes=3),
                reason="telegram_timeout",
                consecutive_failures=2,
                last_success_at=observed_at - timedelta(minutes=5),
            ),
            AlertDeliveryFailure(
                observed_at=observed_at - timedelta(minutes=1),
                reason="telegram_rate_limited",
                consecutive_failures=3,
                last_success_at=observed_at - timedelta(minutes=5),
            ),
        )
    )

    assert len(report.recent_failures) == 2
    assert report.recent_failures[0].reason == "telegram_rate_limited"
    assert report.recent_failures[0].consecutive_failures == 3
    assert report.recent_failures[1].reason == "telegram_timeout"


def test_alert_failure_log_honors_limit_and_sorts_newest_first() -> None:
    observed_at = datetime(2026, 3, 17, 14, 10, tzinfo=UTC)
    service = OperationsOverviewService()

    report = service.build_alert_failure_log(
        (
            AlertDeliveryFailure(observed_at=observed_at - timedelta(minutes=5), reason="old"),
            AlertDeliveryFailure(observed_at=observed_at - timedelta(minutes=2), reason="middle"),
            AlertDeliveryFailure(observed_at=observed_at - timedelta(minutes=1), reason="new"),
        ),
        limit=2,
    )

    assert [failure.reason for failure in report.recent_failures] == ["new", "middle"]
