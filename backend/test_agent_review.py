from __future__ import annotations

import json
import os
from datetime import date

from app.agents.tradingagents_reviewer import TradingAgentsReviewConfig, TradingAgentsReviewer


def main() -> int:
    ticker = input("Ticker: ").strip().upper()
    if not ticker:
        print("Ticker is required.")
        return 2

    trade_date = input(f"Date [{date.today().isoformat()}]: ").strip() or None
    config = TradingAgentsReviewConfig.from_env(os.environ)
    reviewer = TradingAgentsReviewer(config)
    result = reviewer.review(ticker, trade_date)

    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0 if result.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
