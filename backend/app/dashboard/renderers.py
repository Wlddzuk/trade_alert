from __future__ import annotations

from html import escape

from app.api.dashboard_models import DashboardPageModel


def render_dashboard_page(page: DashboardPageModel) -> str:
    sections = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='utf-8'>",
        "  <title>Buy Signal Dashboard</title>",
        "</head>",
        "<body>",
        "  <main data-dashboard='read-only'>",
        _render_header(page),
        _render_overview(page),
    ]

    if page.review_feed is not None and page.pnl_summary is not None:
        sections.append(_render_logs(page))
        sections.append(_render_trade_review(page))
        sections.append(_render_pnl(page))

    sections.extend(["  </main>", "</body>", "</html>"])
    return "\n".join(sections)


def _render_header(page: DashboardPageModel) -> str:
    return (
        "    <header>"
        f"<p>{escape(page.overview.read_only_label)}</p>"
        f"<p>{escape(page.overview.primary_workflow_label)}</p>"
        "<nav>Overview | Logs | Trade Review | Paper P&amp;L</nav>"
        "</header>"
    )


def _render_overview(page: DashboardPageModel) -> str:
    overview = page.overview.overview
    incident_report = page.overview.incident_report
    provider_items = "".join(
        (
            "<li>"
            f"{escape(item.provider)} {escape(item.capability)} "
            f"status={escape(item.status)} age={item.freshness_age_seconds} threshold={item.threshold_seconds}"
            "</li>"
        )
        for item in overview.provider_freshness
    )
    return (
        "    <section id='overview'>"
        "<h1>Status Overview</h1>"
        f"<p>Status: {escape(overview.status.value)}</p>"
        f"<p>{escape(overview.headline)}</p>"
        f"<p>Session: {escape(overview.runtime_phase.value)}</p>"
        f"<p>Scanner loop: {escape(overview.scanner_loop.summary)}</p>"
        f"<p>Alert delivery: {escape(overview.alert_delivery.summary)}</p>"
        f"<p>Recent critical issues: {len(incident_report.recent_critical_issues)}</p>"
        f"<p>Recently resolved incidents: {len(incident_report.recently_resolved)}</p>"
        f"<ul>{provider_items}</ul>"
        "</section>"
    )


def _render_logs(page: DashboardPageModel) -> str:
    incident_report = page.overview.incident_report
    critical = "".join(
        (
            "<li>"
            f"{escape(item.title)}: {escape(item.summary)}"
            "</li>"
        )
        for item in incident_report.recent_critical_issues
    )
    resolved = "".join(
        (
            "<li>"
            f"{escape(item.title)}: {escape(item.summary)}"
            "</li>"
        )
        for item in incident_report.recently_resolved
    )
    return (
        "    <section id='logs'>"
        "<h2>Logs</h2>"
        "<p>Observational only. Recent issues stay separate from the landing overview.</p>"
        "<h3>Recent critical issues</h3>"
        f"<ul>{critical}</ul>"
        "<h3>Recently resolved incidents</h3>"
        f"<ul>{resolved}</ul>"
        "</section>"
    )


def _render_trade_review(page: DashboardPageModel) -> str:
    review_feed = page.review_feed
    assert review_feed is not None

    groups = []
    for day in review_feed.days:
        trades = "".join(
            (
                "<li>"
                f"{escape(trade.symbol)} {trade.trade_id} pnl={trade.realized_pnl} "
                f"exit={escape(trade.exit_reason or 'unknown')} "
                f"raw-events={len(trade.raw_events)}"
                "</li>"
            )
            for trade in day.trades
        )
        groups.append(
            "<section class='trade-day'>"
            f"<h3>{day.trading_day.isoformat()}</h3>"
            f"<p>Trades: {day.trade_count} | Realized P&amp;L: {day.realized_pnl}</p>"
            "<p>Raw lifecycle events remain secondary detail.</p>"
            f"<ul>{trades}</ul>"
            "</section>"
        )
    return (
        "    <section id='trade-review'>"
        "<h2>Trade Review</h2>"
        "<p>Summary-first trade review with raw lifecycle events kept secondary.</p>"
        + "".join(groups)
        + "</section>"
    )


def _render_pnl(page: DashboardPageModel) -> str:
    pnl_summary = page.pnl_summary
    assert pnl_summary is not None
    history_rows = "".join(
        (
            "<li>"
            f"{row.trading_day.isoformat()} pnl={row.realized_pnl} trades={row.trade_count} win-rate={row.win_rate}"
            "</li>"
        )
        for row in pnl_summary.history
    )
    return (
        "    <section id='pnl'>"
        "<h2>Paper P&amp;L</h2>"
        f"<p>Today: {pnl_summary.today.trading_day.isoformat()} realized={pnl_summary.today.realized_pnl}</p>"
        f"<p>Today trades: {pnl_summary.today.trade_count} | Today win rate: {pnl_summary.today.win_rate}</p>"
        f"<p>Cumulative realized P&amp;L: {pnl_summary.cumulative_realized_pnl}</p>"
        f"<p>Cumulative trade count: {pnl_summary.cumulative_trade_count} | Cumulative win rate: {pnl_summary.cumulative_win_rate}</p>"
        "<h3>Day-by-day history</h3>"
        f"<ul>{history_rows}</ul>"
        "</section>"
    )
