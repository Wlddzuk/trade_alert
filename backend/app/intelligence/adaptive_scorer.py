"""Adaptive scorer — learns from historical trade outcomes to adjust signal scores.

The adaptive scorer analyses past trade results and generates score adjustments
across four dimensions:
1. Catalyst type performance (which catalyst tags have the best win rates)
2. RVOL range performance (what daily RVOL levels correlate with wins)
3. Time-of-day performance (what hours produce the best results)
4. Sentiment accuracy (how often the LLM's bullish calls were correct)

It requires a minimum sample size before applying any adjustments to avoid
overfitting on small samples.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from .models import AdaptiveAdjustment, OutcomeRecord, SentimentDirection, TradeOutcome
from .outcome_store import OutcomeStore

logger = logging.getLogger(__name__)

_MIN_SAMPLE_SIZE = 10  # Minimum trades before applying any adjustment
_MIN_DIMENSION_SAMPLES = 5  # Minimum samples per dimension (e.g., per catalyst type)


def _win_rate(records: list[OutcomeRecord]) -> float | None:
    if not records:
        return None
    wins = sum(1 for r in records if r.outcome == TradeOutcome.WIN)
    return wins / len(records)


def _baseline_win_rate(all_records: list[OutcomeRecord]) -> float:
    rate = _win_rate(all_records)
    return rate if rate is not None else 0.5


class AdaptiveScorer:
    """Generates score adjustments based on historical trade outcomes."""

    def __init__(
        self,
        outcome_store: OutcomeStore,
        *,
        min_sample_size: int = _MIN_SAMPLE_SIZE,
        min_dimension_samples: int = _MIN_DIMENSION_SAMPLES,
    ) -> None:
        self.outcome_store = outcome_store
        self.min_sample_size = min_sample_size
        self.min_dimension_samples = min_dimension_samples

    def compute_adjustment(
        self,
        *,
        catalyst_tag: str,
        daily_rvol: Decimal | None = None,
        hour_of_day: int | None = None,
        sentiment_direction: str | None = None,
    ) -> AdaptiveAdjustment:
        """Compute score adjustment based on historical performance for the given features."""
        all_closed = self.outcome_store.get_closed_records()

        if len(all_closed) < self.min_sample_size:
            return AdaptiveAdjustment(
                catalyst_type_adjustment=Decimal("0"),
                rvol_range_adjustment=Decimal("0"),
                time_of_day_adjustment=Decimal("0"),
                sentiment_accuracy_adjustment=Decimal("0"),
                sample_size=len(all_closed),
                reasoning=f"Insufficient data ({len(all_closed)}/{self.min_sample_size} trades needed)",
            )

        baseline = _baseline_win_rate(all_closed)
        reasons: list[str] = []

        # 1. Catalyst type adjustment (-10 to +10)
        catalyst_adj = self._catalyst_adjustment(catalyst_tag, all_closed, baseline, reasons)

        # 2. RVOL range adjustment (-5 to +5)
        rvol_adj = self._rvol_adjustment(daily_rvol, all_closed, baseline, reasons)

        # 3. Time-of-day adjustment (-5 to +5)
        tod_adj = self._time_of_day_adjustment(hour_of_day, all_closed, baseline, reasons)

        # 4. Sentiment accuracy adjustment (-5 to +5)
        sentiment_adj = self._sentiment_adjustment(sentiment_direction, all_closed, baseline, reasons)

        adjustment = AdaptiveAdjustment(
            catalyst_type_adjustment=catalyst_adj,
            rvol_range_adjustment=rvol_adj,
            time_of_day_adjustment=tod_adj,
            sentiment_accuracy_adjustment=sentiment_adj,
            sample_size=len(all_closed),
            reasoning=" | ".join(reasons) if reasons else "No significant deviations",
        )

        logger.info(
            "Adaptive adjustment: total=%s (catalyst=%s, rvol=%s, tod=%s, sent=%s) [%d trades]",
            adjustment.total_adjustment,
            catalyst_adj,
            rvol_adj,
            tod_adj,
            sentiment_adj,
            len(all_closed),
        )
        return adjustment

    def _catalyst_adjustment(
        self,
        catalyst_tag: str,
        all_closed: list[OutcomeRecord],
        baseline: float,
        reasons: list[str],
    ) -> Decimal:
        """How well does this catalyst type perform vs baseline?"""
        by_catalyst = [r for r in all_closed if r.catalyst_tag == catalyst_tag]
        if len(by_catalyst) < self.min_dimension_samples:
            return Decimal("0")

        catalyst_wr = _win_rate(by_catalyst)
        if catalyst_wr is None:
            return Decimal("0")

        delta = catalyst_wr - baseline
        # Scale: 20pp above baseline = +10, 20pp below = -10
        adj = Decimal(str(round(delta * 50, 1)))
        adj = max(Decimal("-10"), min(Decimal("10"), adj))
        if adj != Decimal("0"):
            reasons.append(f"catalyst={catalyst_tag} wr={catalyst_wr:.0%} vs {baseline:.0%} → {adj:+}")
        return adj

    def _rvol_adjustment(
        self,
        daily_rvol: Decimal | None,
        all_closed: list[OutcomeRecord],
        baseline: float,
        reasons: list[str],
    ) -> Decimal:
        """How well do trades in this RVOL range perform?"""
        if daily_rvol is None:
            return Decimal("0")

        # Bucket RVOL: 1-2x, 2-4x, 4-8x, 8+x
        def _rvol_bucket(rvol: Decimal | None) -> str | None:
            if rvol is None:
                return None
            v = float(rvol)
            if v < 2:
                return "low"
            if v < 4:
                return "medium"
            if v < 8:
                return "high"
            return "extreme"

        target_bucket = _rvol_bucket(daily_rvol)
        if target_bucket is None:
            return Decimal("0")

        bucket_records = [r for r in all_closed if _rvol_bucket(r.daily_rvol) == target_bucket]
        if len(bucket_records) < self.min_dimension_samples:
            return Decimal("0")

        rvol_wr = _win_rate(bucket_records)
        if rvol_wr is None:
            return Decimal("0")

        delta = rvol_wr - baseline
        adj = Decimal(str(round(delta * 25, 1)))
        adj = max(Decimal("-5"), min(Decimal("5"), adj))
        if adj != Decimal("0"):
            reasons.append(f"rvol_bucket={target_bucket} wr={rvol_wr:.0%} → {adj:+}")
        return adj

    def _time_of_day_adjustment(
        self,
        hour_of_day: int | None,
        all_closed: list[OutcomeRecord],
        baseline: float,
        reasons: list[str],
    ) -> Decimal:
        """How well do trades entered at this hour perform?"""
        if hour_of_day is None:
            return Decimal("0")

        # Group nearby hours: ±1 hour window
        nearby = [
            r for r in all_closed
            if abs(r.hour_of_day - hour_of_day) <= 1 or abs(r.hour_of_day - hour_of_day) >= 23
        ]
        if len(nearby) < self.min_dimension_samples:
            return Decimal("0")

        hour_wr = _win_rate(nearby)
        if hour_wr is None:
            return Decimal("0")

        delta = hour_wr - baseline
        adj = Decimal(str(round(delta * 25, 1)))
        adj = max(Decimal("-5"), min(Decimal("5"), adj))
        if adj != Decimal("0"):
            reasons.append(f"hour={hour_of_day} wr={hour_wr:.0%} → {adj:+}")
        return adj

    def _sentiment_adjustment(
        self,
        sentiment_direction: str | None,
        all_closed: list[OutcomeRecord],
        baseline: float,
        reasons: list[str],
    ) -> Decimal:
        """How accurate is the LLM's sentiment for this direction?"""
        if sentiment_direction is None:
            return Decimal("0")

        with_sentiment = [r for r in all_closed if r.sentiment_direction == sentiment_direction]
        if len(with_sentiment) < self.min_dimension_samples:
            return Decimal("0")

        sent_wr = _win_rate(with_sentiment)
        if sent_wr is None:
            return Decimal("0")

        is_bullish = sentiment_direction in (
            SentimentDirection.BULLISH.value,
            SentimentDirection.STRONGLY_BULLISH.value,
        )

        # If LLM said bullish and it wins more than baseline → positive adjustment
        # If LLM said bearish and it was right (losses) → also positive (we avoided it)
        if is_bullish:
            delta = sent_wr - baseline
        else:
            # For bearish calls, lower win rate validates the LLM's caution
            delta = baseline - sent_wr

        adj = Decimal(str(round(delta * 25, 1)))
        adj = max(Decimal("-5"), min(Decimal("5"), adj))
        if adj != Decimal("0"):
            reasons.append(f"sentiment={sentiment_direction} accuracy wr={sent_wr:.0%} → {adj:+}")
        return adj

    def get_learning_summary(self) -> dict:
        """Return a summary of what the system has learned."""
        all_closed = self.outcome_store.get_closed_records()
        if not all_closed:
            return {"status": "no_data", "total_trades": 0}

        baseline = _baseline_win_rate(all_closed)

        # Best/worst catalyst types
        catalyst_stats: dict[str, dict] = {}
        for r in all_closed:
            if r.catalyst_tag not in catalyst_stats:
                catalyst_stats[r.catalyst_tag] = {"wins": 0, "total": 0}
            catalyst_stats[r.catalyst_tag]["total"] += 1
            if r.outcome == TradeOutcome.WIN:
                catalyst_stats[r.catalyst_tag]["wins"] += 1

        for tag, stats in catalyst_stats.items():
            stats["win_rate"] = stats["wins"] / stats["total"] if stats["total"] > 0 else 0

        # Best/worst hours
        hour_stats: dict[int, dict] = {}
        for r in all_closed:
            if r.hour_of_day not in hour_stats:
                hour_stats[r.hour_of_day] = {"wins": 0, "total": 0}
            hour_stats[r.hour_of_day]["total"] += 1
            if r.outcome == TradeOutcome.WIN:
                hour_stats[r.hour_of_day]["wins"] += 1

        for hour, stats in hour_stats.items():
            stats["win_rate"] = stats["wins"] / stats["total"] if stats["total"] > 0 else 0

        # LLM accuracy
        with_sentiment = self.outcome_store.get_records_with_sentiment()
        bullish_calls = [r for r in with_sentiment if r.sentiment_direction in ("bullish", "strongly_bullish")]
        bullish_wr = _win_rate(bullish_calls)

        return {
            "status": "active" if len(all_closed) >= self.min_sample_size else "learning",
            "total_trades": len(all_closed),
            "baseline_win_rate": f"{baseline:.1%}",
            "catalyst_performance": {
                tag: {"win_rate": f"{s['win_rate']:.1%}", "trades": s["total"]}
                for tag, s in sorted(catalyst_stats.items(), key=lambda x: x[1]["win_rate"], reverse=True)
            },
            "best_hours": {
                str(h): {"win_rate": f"{s['win_rate']:.1%}", "trades": s["total"]}
                for h, s in sorted(hour_stats.items(), key=lambda x: x[1]["win_rate"], reverse=True)[:5]
            },
            "llm_sentiment": {
                "total_analyzed": len(with_sentiment),
                "bullish_calls": len(bullish_calls),
                "bullish_win_rate": f"{bullish_wr:.1%}" if bullish_wr is not None else "n/a",
            },
        }
