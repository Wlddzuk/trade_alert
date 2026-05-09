# TradingAgents Review Setup

This is the optional second-opinion layer for scanner detections.

The scanner should still decide whether a setup exists. TradingAgents should only review a small number of already-qualified setups, then the result can be saved and included in a Telegram alert.

## Cost Posture

Defaults are intentionally cheap:

- LLM provider: `google`
- Deep model: `gemini-2.5-flash`
- Quick model: `gemini-2.5-flash`
- Debate rounds: `1`
- Risk discussion rounds: `1`
- Data vendors: `yfinance`
- Daily cap: `10` reviews per backend process

Do not run the reviewer across the whole universe.

## Environment

Required for Gemini:

```bash
export GOOGLE_API_KEY="your-google-ai-studio-key"
```

Optional overrides:

```bash
export TRADINGAGENTS_REVIEW_ENABLED="true"
export TRADINGAGENTS_REVIEW_MIN_SCORE="85"
export TRADINGAGENTS_REVIEW_TIMEOUT_SECONDS="180"
export TRADINGAGENTS_LLM_PROVIDER="google"
export TRADINGAGENTS_MODEL="gemini-2.5-flash"
export TRADINGAGENTS_MAX_REVIEWS_PER_DAY="10"
export TRADINGAGENTS_REPO_PATH="/path/to/TradingAgents"
```

For Kimi through OpenRouter later:

```bash
export OPENROUTER_API_KEY="your-openrouter-key"
export TRADINGAGENTS_LLM_PROVIDER="openrouter"
export TRADINGAGENTS_MODEL="moonshotai/kimi-k2.5"
```

## Manual Test

From `buy_signal/backend`:

```bash
python test_agent_review.py
```

The script asks for a ticker and optional date, then prints the raw TradingAgents decision payload.

## Integration Rule

Only call this after the scanner emits a strong setup, for example:

```text
status == "trigger_ready"
score >= chosen threshold
daily review cap not reached
no cached review for ticker + date
```

If the reviewer fails or hits the cap, the scanner should continue and the alert should say that the agent review was unavailable.

Current implementation:

- disabled by default
- enable with `TRADINGAGENTS_REVIEW_ENABLED=true`
- runs only for `trigger_ready` alerts at or above `TRADINGAGENTS_REVIEW_MIN_SCORE`
- enforces `TRADINGAGENTS_MAX_REVIEWS_PER_DAY`
- stores JSONL results at `backend/data/tradingagents/agent_reviews.jsonl`
- includes the review status/decision in the Telegram setup alert
