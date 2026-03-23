# Buy Signal

Buy Signal is an operator-facing momentum scanner and semi-automated paper-trading workflow for news-driven US equities.

The shipped `v1.0` shape is:

- scanner-first
- Telegram-led for alerts and operator decisions
- paper-trading-first, not live execution
- read-only dashboard for monitoring, logs, trade review, and paper P&L

This README is the practical operator and developer guide for the current repo: what exists, how to run it, what to configure, and how to interpret the signals.

## What This Tool Does

At a high level, the system is designed to:

- ingest market data and news
- filter to a US-equity universe
- rank momentum-pullback candidates
- identify trigger-ready setups
- send Telegram alerts for qualifying setups
- allow human approval, rejection, or adjustment
- simulate paper-trade lifecycle events
- expose a secondary read-only dashboard for review

The intended workflow is:

1. The scanner surfaces ranked candidates.
2. A valid setup becomes `building` or `trigger_ready`.
3. If the setup passes entry-quality and session rules, it becomes actionable in Telegram.
4. You approve, reject, or adjust the setup.
5. The paper broker tracks the trade and exits.
6. Audit logs, trade review, and P&L remain visible in the dashboard.

## Current Repo State

This repo contains a working Python backend plus archived planning and verification artifacts for `v1.0`.

Important limitation:

- The repo has the Telegram workflow contracts, rendering, callback handling, and runtime delivery abstractions.
- It does not currently include a concrete production Telegram Bot API transport implementation that reads a bot token from environment variables and sends real HTTPS requests to Telegram.

That means:

- the Telegram workflow is modeled and tested
- the webhook/callback boundary exists
- but you still need to wire a real `TelegramTransport` implementation for live Telegram delivery

## Repo Layout

- [backend](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend): Python backend
- [backend/app/main.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/main.py): ASGI app entrypoint and runtime composition
- [backend/app/config.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/config.py): supported environment variables
- [backend/app/scanner](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/scanner): scanner, setup validity, trigger, invalidation, ranking
- [backend/app/alerts](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/alerts): Telegram message rendering, alert emission, approval workflow, action execution
- [backend/app/api](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/api): dashboard routes and Telegram webhook routes
- [backend/app/paper](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/paper): paper broker and exits
- [backend/app/audit](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/audit): lifecycle log, trade review, P&L
- [backend/tests](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/tests): current test suite
- [.planning/milestones/v1.0-ROADMAP.md](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/.planning/milestones/v1.0-ROADMAP.md): archived shipped milestone scope
- [.planning/milestones/v1.0-MILESTONE-AUDIT.md](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/.planning/milestones/v1.0-MILESTONE-AUDIT.md): archived milestone audit

## Requirements

- Python `3.12+`
- `uv` recommended for test execution and virtualenv management

The backend package metadata is in [backend/pyproject.toml](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/pyproject.toml).

## Quick Start

### 1. Enter the backend

```bash
cd backend
```

### 2. Create or use a virtual environment

If you use `uv`:

```bash
uv sync --dev
```

If you already have the checked-in local env, use that instead.

### 3. Run the tests

```bash
uv run pytest
```

### 4. Run the ASGI app

The ASGI callable is:

- [backend/app/main.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/main.py)
- object: `app`

If you have `uvicorn` installed:

```bash
uvicorn app.main:app --app-dir backend --reload
```

If you prefer running from inside `backend`:

```bash
cd backend
uvicorn app.main:app --reload
```

Notes:

- `uvicorn` is not declared in [backend/pyproject.toml](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/pyproject.toml), so install it separately if needed.
- The root dashboard path redirects to `/dashboard`.
- Telegram webhook route is `/telegram/webhook`.

## Supported Environment Variables

The repo currently reads these variables in [backend/app/config.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/config.py):

### Provider Settings

- `POLYGON_API_KEY`
- `POLYGON_BASE_URL`
- `POLYGON_TIMEOUT_SECONDS`
- `BENZINGA_API_KEY`
- `BENZINGA_BASE_URL`
- `BENZINGA_TIMEOUT_SECONDS`

### Dashboard Auth

- `DASHBOARD_PASSWORD`
- `DASHBOARD_SESSION_SECRET`
- `DASHBOARD_SESSION_COOKIE_NAME`

Example:

```bash
export POLYGON_API_KEY="your-polygon-key"
export BENZINGA_API_KEY="your-benzinga-key"
export DASHBOARD_PASSWORD="choose-a-password"
export DASHBOARD_SESSION_SECRET="choose-a-long-random-secret"
```

## Telegram Setup

## Do You Need a Telegram Bot Token?

Yes, if you want real Telegram delivery.

But there is an important distinction:

- Telegram bot setup is necessary for live use
- this repo does not yet include the final concrete Bot API HTTP sender that consumes the token directly

In code terms:

- the system defines a `TelegramTransport` protocol in [backend/app/alerts/telegram_transport.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/alerts/telegram_transport.py)
- runtime delivery is built around that abstraction in [backend/app/alerts/telegram_runtime.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/alerts/telegram_runtime.py) and [backend/app/main.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/main.py)
- but a production transport class that calls the real Telegram Bot API is not present in this repo yet

So the README guidance is:

- create the bot token now if you plan to run this for real
- keep the token out of git
- wire it into a real transport implementation before expecting live Telegram sends

## How To Create the Bot Token

1. Open Telegram.
2. Search for `@BotFather`.
3. Start the chat.
4. Run `/newbot`.
5. Choose a bot name.
6. Choose a bot username ending in `bot`.
7. BotFather will return a token.

Treat that token like a password.

## How To Get Your Chat ID

You also need the chat ID the bot will send messages to.

Common approaches:

1. Start a chat with your bot and send it a message.
2. Use the Telegram Bot API `getUpdates` endpoint after messaging the bot.
3. Inspect the incoming webhook payload once your bot is wired.

The codebase already uses the concept of `operator_chat_id` in the runtime composition, for example in [backend/app/main.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/main.py#L110) and [backend/app/alerts/alert_emission.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/alerts/alert_emission.py).

## Recommended Future Env Vars for Live Telegram Wiring

These are not currently read by the repo, but if you add the missing production transport, these are the obvious variables to use:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_OPERATOR_CHAT_ID`
- `TELEGRAM_WEBHOOK_SECRET` or similar, if you add webhook verification

That would let you wire:

- outbound alert delivery
- Telegram callback routing
- operator chat targeting

## Dashboard Usage

The dashboard is intentionally secondary and read-only.

Implemented routes include:

- `/dashboard`
- `/dashboard/logs`
- `/dashboard/trades`
- `/dashboard/pnl`
- `/dashboard/login`

Behavior shown in tests:

- unauthenticated access returns a login page
- successful login sets a session cookie
- the overview is status-first
- logs, trade review, and P&L stay observational
- the dashboard is explicitly not the primary control surface

See:

- [backend/tests/dashboard/test_dashboard_serving.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/tests/dashboard/test_dashboard_serving.py)
- [backend/tests/dashboard/test_dashboard_auth.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/tests/dashboard/test_dashboard_auth.py)

## Telegram Webhook Usage

Implemented route:

- `POST /telegram/webhook`

Behavior:

- accepts JSON updates
- processes callback queries and plain messages
- returns `202 ignored` if no callback or message payload is present

See:

- [backend/app/api/telegram_routes.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/api/telegram_routes.py)
- [backend/app/api/telegram_callbacks.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/api/telegram_callbacks.py)

## How To Understand the Signals

This is the most important operator section.

The system is not a generic stock screener. It is opinionated around news-driven momentum pullbacks.

### Core Signal Idea

The scanner is looking for:

- a fresh catalyst
- meaningful day move
- strong relative volume
- a pullback after expansion
- a reclaim or continuation trigger
- enough quality to be worth operator attention

### Default Strategy Thresholds

From [backend/app/scanner/strategy_defaults.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/scanner/strategy_defaults.py), the default thresholds are:

- catalyst age: `<= 90 minutes`
- min day move: `8%`
- min daily RVOL: `2.0x`
- min short-term RVOL: `1.5x`
- pullback retracement window: `35%` to `60%`
- preferred trigger bar interval: `15 seconds`
- fallback trigger bar interval: `60 seconds`

These defaults tell you the style:

- not slow swing setups
- not random gapper noise
- specifically fast, news-led momentum names with structured pullbacks

### What Makes a Setup Valid

From [backend/app/scanner/setup_validity.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/scanner/setup_validity.py), a setup is considered valid only if all of these are true:

- there is a catalyst
- the catalyst is still fresh
- the day move is large enough
- daily RVOL is high enough
- short-term RVOL is high enough
- price is above VWAP
- `EMA 9 > EMA 20`
- pullback retracement is inside the allowed range

If any of those fail, the setup becomes invalid with a primary invalid reason.

Common invalid reasons include:

- missing catalyst
- stale catalyst
- insufficient day move
- insufficient daily RVOL
- insufficient short-term RVOL
- missing trend context
- below VWAP
- EMA misalignment
- pullback too shallow
- pullback too deep

### What “Building”, “Trigger Ready”, and “Invalidated” Mean

From [backend/app/scanner/strategy_tags.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/scanner/strategy_tags.py):

- `building`: valid setup, but no trigger yet
- `trigger_ready`: valid setup with a trigger detected
- `invalidated`: setup is no longer valid or explicitly broken

Interpretation:

- `building` means “watch this”
- `trigger_ready` means “this is the moment to evaluate entry”
- `invalidated` means “do not treat this as a live setup anymore”

### How the Trigger Works

From [backend/app/scanner/trigger_logic.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/scanner/trigger_logic.py), the trigger is the first break of the prior bar high.

In practice:

- preferred timeframe is `15s`
- fallback is `1m`
- the system also records whether the trigger bar had bullish confirmation

So when you see `trigger_ready`, it means the system detected a first-break continuation event, not just “the stock is moving.”

### How a Setup Gets Invalidated

From [backend/app/scanner/invalidation.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/scanner/invalidation.py), a setup can be invalidated for reasons such as:

- setup already invalid
- contradictory catalyst
- stale catalyst
- weak relative volume
- pullback too deep
- pullback low broken
- lost intraday context
- halted
- dead move after repeated failed breakouts

This matters because a setup can look strong visually but still be mechanically outside the model.

### What the Score Means

From [backend/app/scanner/strategy_ranking.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/scanner/strategy_ranking.py), the score is a quality-first `0-100` ranking.

Higher score generally means:

- fresher catalyst
- larger day move
- stronger daily RVOL
- stronger short-term RVOL
- acceptable pullback structure
- lighter pullback volume
- trigger confirmation

Important:

- score is ranking, not certainty
- a lower-scored valid setup can still work
- a higher-scored setup is only “better by the model,” not guaranteed

### What Rank Means

Rank is the ordering among currently surfaced candidates.

Example:

- `Score / Rank: 96 / #1`

means:

- this setup scored `96`
- it is currently the top-ranked surfaced setup

### What the Telegram Alert States Mean

From [backend/app/alerts/models.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/alerts/models.py), pre-entry alerts can be:

- `watch`
- `actionable`
- `blocked`
- `rejected`

Interpretation:

- `watch`: setup is building, not ready for entry
- `actionable`: trigger-ready and allowed by quality plus session rules
- `blocked`: trigger-ready but temporarily blocked by a session rule
- `rejected`: trigger-ready but fails a hard entry-quality gate

### Why a Trigger-Ready Setup Can Still Be Blocked or Rejected

A setup can be `trigger_ready` at the scanner level and still not be tradable.

The entry workflow combines:

- trade-quality gates
- session guards

See:

- [backend/app/risk/trade_gates.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/risk/trade_gates.py)
- [backend/app/risk/models.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/risk/models.py)
- [backend/tests/operator_workflow/test_actionability.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/tests/operator_workflow/test_actionability.py)

#### Rejected

A setup becomes `rejected` when a hard trade-quality gate fails, for example:

- spread too wide
- insufficient liquidity
- missing stop
- stop distance too wide for allowed sizing

#### Blocked

A setup becomes `blocked` when the structure is okay, but the session rules say “not now,” for example:

- cooldown active after a loss
- max daily loss reached
- max open positions reached
- entry cutoff reached

This distinction is important:

- `rejected` means “bad trade quality”
- `blocked` means “good enough structurally, but not allowed right now”

### How To Read a Telegram Alert

The rendered pre-entry alert format comes from [backend/app/alerts/telegram_renderer.py](/Users/waliddali-bey/Documents/GettingStarted/buy_signal/backend/app/alerts/telegram_renderer.py).

A typical alert includes:

- state and symbol
- catalyst tag and headline
- setup stage
- entry, stop, and target
- score and rank
- supporting context
- status reason when blocked or rejected

Typical buttons:

- `Approve`
- `Adjust`
- `Reject`

Once a trade is open, the workflow can send:

- `Close`
- `Adjust Stop`
- `Adjust Target`

### Practical Operator Reading Guide

When a symbol appears, read it in this order:

1. Is it `building`, `trigger_ready`, or `invalidated`?
2. How fresh is the catalyst?
3. Is the move strong enough and volume expanded enough to matter?
4. Is the pullback still structurally healthy?
5. Is the system saying `actionable`, `blocked`, or `rejected`?
6. If it is actionable, do the proposed entry, stop, and target make sense for the tape you see?

Good mental model:

- scanner stage answers: “is the setup structurally there?”
- entry disposition answers: “am I allowed to take it now?”

## Suggested `.env` For Current Repo

For the code that exists today, a minimal local setup looks like:

```bash
POLYGON_API_KEY=your_polygon_key
BENZINGA_API_KEY=your_benzinga_key
DASHBOARD_PASSWORD=choose_a_password
DASHBOARD_SESSION_SECRET=choose_a_long_random_secret
```

For future live Telegram wiring, you will likely also want:

```bash
TELEGRAM_BOT_TOKEN=from_botfather
TELEGRAM_OPERATOR_CHAT_ID=your_chat_id
```

Again: those Telegram variables are not consumed by the current repo yet.

## Recommended Next Improvement

If you want this repo to be runnable end to end with a real Telegram bot, the next practical step is:

1. add a concrete Bot API transport implementation for `TelegramTransport`
2. read `TELEGRAM_BOT_TOKEN` and `TELEGRAM_OPERATOR_CHAT_ID` from env
3. wire transport creation into the runtime entrypoint
4. document webhook registration for the bot

If you want, I can add that next, or I can add a separate `docs/signals.md` and `docs/telegram-setup.md` split out from this README.
