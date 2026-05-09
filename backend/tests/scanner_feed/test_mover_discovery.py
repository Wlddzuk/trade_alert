from __future__ import annotations

from app import main


def test_parse_movers_from_quotes_handles_nested_yahoo_values() -> None:
    movers = main._parse_movers_from_quotes(
        [
            {
                "symbol": "ABCD",
                "regularMarketChangePercent": {"raw": 6.25},
                "regularMarketPrice": {"raw": 2.15},
                "regularMarketVolume": "100,000",
                "averageDailyVolume3Month": "50,000",
                "regularMarketPreviousClose": {"raw": 2.00},
                "regularMarketDayHigh": {"raw": 2.20},
                "regularMarketDayLow": {"raw": 1.95},
            },
            {
                "symbol": "SLOW",
                "regularMarketChangePercent": {"raw": 2.0},
                "regularMarketPrice": {"raw": 10.00},
            },
        ],
        min_gap_percent=5.0,
    )

    assert len(movers) == 1
    assert movers[0]["symbol"] == "ABCD"
    assert movers[0]["change_percent"] == 6.25
    assert movers[0]["price"] == 2.15
    assert movers[0]["volume"] == 100_000
    assert movers[0]["rvol"] == 2.0


def test_discover_movers_falls_back_to_equity_query(monkeypatch) -> None:
    calls = []

    def fake_screen(query, **kwargs):
        calls.append((query, kwargs))
        if query == "day_gainers":
            return {"quotes": []}
        return {
            "quotes": [
                {
                    "symbol": "FAST",
                    "percentchange": 7.5,
                    "intradayprice": 3.21,
                    "dayvolume": 250_000,
                    "avgdailyvol3m": 100_000,
                    "regularMarketPreviousClose": 2.98,
                }
            ]
        }

    monkeypatch.setattr(main.yf, "screen", fake_screen)

    movers = main._discover_movers()

    assert [mover["symbol"] for mover in movers] == ["FAST"]
    assert calls[0][0] == "day_gainers"
    assert len(calls) == 2
