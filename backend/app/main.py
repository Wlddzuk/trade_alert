from __future__ import annotations

from app.api.dashboard_routes import DashboardRoutes


class BuySignalApp:
    def __init__(self) -> None:
        self.dashboard = DashboardRoutes()


def create_app() -> BuySignalApp:
    return BuySignalApp()


app = create_app()
