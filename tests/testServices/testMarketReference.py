"""Tests for reading a ticker or a pasted market address."""

from __future__ import annotations

import pytest

from wagerBook.models.wager import Platform
from wagerBook.services.marketReference import MarketReference, parseMarketReference


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://kalshi.com/markets/senatetx/texas-senate-winner/senatetx-26",
         MarketReference(Platform.kalshi, "SENATETX-26")),
        ("kalshi.com/markets/senatetx/texas-senate-winner/senatetx-26?ref=share",
         MarketReference(Platform.kalshi, "SENATETX-26")),
        ("https://www.kalshi.com/markets/kxirandemocracy/",
         MarketReference(Platform.kalshi, "KXIRANDEMOCRACY")),
        ("https://polymarket.com/event/arizona-governor-winner-2026",
         MarketReference(Platform.polymarket, "arizona-governor-winner-2026")),
        ("https://polymarket.com/event/arizona-governor-winner-2026/"
         "will-the-republican-win-the-arizona-governor-race-in-2026?tid=1#x",
         MarketReference(Platform.polymarket,
                         "will-the-republican-win-the-arizona-governor-race-in-2026")),
        ("https://polymarket.us/market/chiefs-super-bowl-lx",
         MarketReference(Platform.polymarket, "chiefs-super-bowl-lx")),
        ("  SENATETX-26-R  ", MarketReference(None, "SENATETX-26-R")),
        ("will-the-republican-win-the-arizona-governor-race-in-2026",
         MarketReference(None, "will-the-republican-win-the-arizona-governor-race-in-2026")),
    ],
)
def testAddressesAndTickers(text: str, expected: MarketReference) -> None:
    assert parseMarketReference(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "https://example.com/markets/x",
                                  "https://kalshi.com/", "https://polymarket.com/"])
def testNothingUsable(text: str) -> None:
    assert parseMarketReference(text) is None
