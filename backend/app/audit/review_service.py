from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC
from decimal import Decimal

from .models import LifecycleEvent
from .review_models import CompletedTradeReview, TradeReviewDay, TradeReviewFeed
from .trade_review import build_trade_reviews


class TradeReviewService:
    def build_completed_trade_feed(self, events: Iterable[LifecycleEvent]) -> TradeReviewFeed:
        all_events = tuple(events)
        completed_reviews: list[CompletedTradeReview] = []
        for review in build_trade_reviews(all_events):
            if review.closed_at is None or review.close_price is None or review.entry_price is None:
                continue
            if review.realized_pnl is None or review.quantity is None or review.opened_at is None:
                continue
            raw_events = tuple(
                event
                for event in all_events
                if event.trade_id == review.trade_id
                or (review.alert_id is not None and event.alert_id == review.alert_id)
            )
            completed_reviews.append(
                CompletedTradeReview(
                    trade_id=review.trade_id,
                    symbol=review.symbol,
                    trading_day=review.closed_at.astimezone(UTC).date(),
                    closed_at=review.closed_at,
                    opened_at=review.opened_at,
                    entry_decision=review.entry_decision,
                    operator_commands=review.operator_commands,
                    entry_price=review.entry_price,
                    close_price=review.close_price,
                    quantity=review.quantity,
                    exit_reason=review.exit_reason,
                    realized_pnl=review.realized_pnl,
                    raw_events=raw_events,
                )
            )

        completed_reviews.sort(key=lambda review: review.closed_at, reverse=True)

        grouped: dict = defaultdict(list)
        for review in completed_reviews:
            grouped[review.trading_day].append(review)

        days = tuple(
            TradeReviewDay(
                trading_day=trading_day,
                trades=tuple(trades),
                realized_pnl=sum((trade.realized_pnl for trade in trades), start=Decimal("0")),
                trade_count=len(trades),
                win_count=sum(1 for trade in trades if trade.realized_pnl > 0),
            )
            for trading_day, trades in sorted(grouped.items(), reverse=True)
        )
        return TradeReviewFeed(days=days, total_trades=len(completed_reviews))
