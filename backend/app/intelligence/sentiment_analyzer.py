"""LLM-powered sentiment analysis for news catalysts.

Uses OpenAI to interpret headlines and determine:
- Sentiment direction (strongly bullish → strongly bearish)
- Catalyst quality (Tier 1 → Noise)
- Confidence and expected price impact
- Human-readable reasoning
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from .models import CatalystQuality, SentimentDirection, SentimentVerdict

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a professional day-trading analyst specialising in momentum setups on US equities.
Your job is to read a news headline (and optional body) for a given stock ticker
and assess its impact on the stock price for the current trading session.

Respond ONLY with valid JSON matching this schema exactly:
{
  "direction": "strongly_bullish" | "bullish" | "neutral" | "bearish" | "strongly_bearish",
  "catalyst_quality": "tier_1" | "tier_2" | "tier_3" | "noise",
  "confidence": <float 0.0 to 1.0>,
  "expected_move_percent": <float or null>,
  "reasoning": "<one-line explanation>"
}

Catalyst quality guide:
- tier_1: FDA approval, major M&A, transformative contract, bankruptcy filing (highest impact)
- tier_2: Earnings beat/miss, analyst upgrade/downgrade, product launch, partnership
- tier_3: Sector rotation, social media buzz, minor analyst mention, conference presentation
- noise: Recycled news, fluff PR, irrelevant to stock price

Be precise. Consider:
1. Is this genuinely NEW information or recycled?
2. How material is the impact to the company's value?
3. For momentum trades: will this attract volume and create a lasting move, or a quick fade?
"""


def _build_user_prompt(symbol: str, headline: str, body: str | None = None) -> str:
    parts = [f"Ticker: {symbol}", f"Headline: {headline}"]
    if body:
        # Limit body to 500 chars to save tokens
        truncated = body[:500] + ("..." if len(body) > 500 else "")
        parts.append(f"Body excerpt: {truncated}")
    return "\n".join(parts)


def _parse_llm_response(raw: str, symbol: str, headline: str) -> SentimentVerdict:
    """Parse the JSON response from the LLM into a SentimentVerdict."""
    # Strip markdown code fences if the LLM wraps response
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    data = json.loads(cleaned)

    direction = SentimentDirection(data["direction"])
    quality = CatalystQuality(data["catalyst_quality"])
    confidence = float(data["confidence"])
    expected_move = data.get("expected_move_percent")
    if expected_move is not None:
        expected_move = float(expected_move)
    reasoning = str(data.get("reasoning", ""))

    return SentimentVerdict(
        headline=headline,
        symbol=symbol,
        direction=direction,
        catalyst_quality=quality,
        confidence=min(1.0, max(0.0, confidence)),
        expected_move_percent=expected_move,
        reasoning=reasoning,
        analyzed_at=datetime.now(UTC),
    )


class SentimentAnalyzer:
    """Analyzes news headlines using OpenAI to produce structured sentiment verdicts."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_tokens: int = 200,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        # In-memory cache: (symbol, headline) → verdict
        self._cache: dict[tuple[str, str], SentimentVerdict] = {}
        # Shared aiohttp session — created lazily, reused across calls
        self._session: Any | None = None

    async def analyze(
        self,
        symbol: str,
        headline: str,
        body: str | None = None,
    ) -> SentimentVerdict | None:
        """Analyze a headline and return a sentiment verdict, or None on failure."""
        cache_key = (symbol, headline)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            verdict = await self._call_llm(symbol, headline, body)
            self._cache[cache_key] = verdict
            logger.info(
                "Sentiment: %s %s → %s (quality=%s, conf=%.2f) — %s",
                symbol,
                headline[:60],
                verdict.direction.value,
                verdict.catalyst_quality.value,
                verdict.confidence,
                verdict.reasoning,
            )
            return verdict
        except Exception:
            logger.exception("Sentiment analysis failed for %s: %s", symbol, headline[:60])
            return None

    async def analyze_batch(
        self,
        items: list[tuple[str, str, str | None]],
    ) -> dict[str, SentimentVerdict]:
        """Analyze multiple (symbol, headline, body) tuples. Returns symbol → verdict."""
        import asyncio

        results: dict[str, SentimentVerdict] = {}
        tasks = []
        for symbol, headline, body in items:
            tasks.append(self.analyze(symbol, headline, body))

        verdicts = await asyncio.gather(*tasks)
        for (symbol, _, _), verdict in zip(items, verdicts):
            if verdict is not None:
                results[symbol] = verdict
        return results

    async def _get_session(self) -> Any:
        """Return (and lazily create) the shared aiohttp session."""
        import aiohttp

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._session

    async def _call_llm(
        self,
        symbol: str,
        headline: str,
        body: str | None,
    ) -> SentimentVerdict:
        """Make the actual OpenAI API call."""
        user_prompt = _build_user_prompt(symbol, headline, body)

        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }

        session = await self._get_session()
        async with session.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

        content = data["choices"][0]["message"]["content"]
        return _parse_llm_response(content, symbol, headline)

    def clear_cache(self) -> None:
        """Clear the in-memory sentiment cache."""
        self._cache.clear()

    async def close(self) -> None:
        """Close the shared aiohttp session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None
