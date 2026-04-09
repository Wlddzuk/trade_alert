#!/bin/bash
# Start the buy_signal app with all env vars loaded
cd "$(dirname "$0")"
set -a && source .env && set +a
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
