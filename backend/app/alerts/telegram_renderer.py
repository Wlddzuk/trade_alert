from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from .models import PreEntryAlert, RenderedTelegramMessage


def _label(value: str | StrEnum) -> str:
    raw = value.value if isinstance(value, StrEnum) else value
    return raw.replace("_", " ").title()


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def render_pre_entry_alert(alert: PreEntryAlert) -> RenderedTelegramMessage:
    lines = [
        f"[{_label(alert.state)}] {alert.symbol}",
        f"Catalyst: {_label(alert.projection.row.catalyst_tag)} | {alert.projection.row.headline}",
        f"Setup: {_label(alert.projection.stage_tag)}",
        (
            "Entry / Stop / Target: "
            f"{_format_decimal(alert.proposal.entry_price)} / "
            f"{_format_decimal(alert.proposal.stop_price)} / "
            f"{_format_decimal(alert.proposal.target_price)}"
        ),
        f"Score / Rank: {alert.projection.score} / #{alert.rank}",
    ]

    if alert.projection.supporting_reasons:
        lines.append(f"Context: {', '.join(alert.projection.supporting_reasons)}")

    if alert.display_reason is not None:
        lines.append(f"Status: {alert.display_reason}")

    return RenderedTelegramMessage(text="\n".join(lines))

