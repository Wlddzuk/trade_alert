from __future__ import annotations

from app.api import DashboardRoutes, TelegramRoutes


class BuySignalApp:
    def __init__(
        self,
        *,
        dashboard: DashboardRoutes | None = None,
        telegram: TelegramRoutes | None = None,
    ) -> None:
        self.dashboard = dashboard or DashboardRoutes()
        self.telegram = telegram or TelegramRoutes()


def create_app(
    *,
    dashboard: DashboardRoutes | None = None,
    telegram: TelegramRoutes | None = None,
) -> BuySignalApp:
    return BuySignalApp(
        dashboard=dashboard,
        telegram=telegram,
    )


app = create_app()
