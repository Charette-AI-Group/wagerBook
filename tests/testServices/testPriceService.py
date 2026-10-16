"""Tests for pricing open wagers, against saved replies from both sites.

The fixtures under tests/fixtures/prices are real replies, trimmed to the
fields the service reads, so the parsing is checked against what the sites
actually send. Nothing here touches the network.
"""

from __future__ import annotations

import io
import json
import urllib.error
from datetime import datetime
from pathlib import Path

import pytest

from wagerBook.models.wager import Platform, Side, Status, Wager
from wagerBook.services.priceService import (
    PriceRequest,
    PriceService,
    kalshiApi,
    labelInTitle,
    polymarketApi,
)
from wagerBook.services.wagerStore import WagerStore

fixtures = Path(__file__).resolve().parents[1] / "fixtures" / "prices"
notFound = "404"


class FakeReply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeSite:
    """Answers each URL from a fixture, a 404, or a dropped connection."""

    def __init__(self, routes: dict[str, object]) -> None:
        self.routes = routes
        self.asked: list[str] = []

    def __call__(self, request, timeout=None):
        url = request.full_url
        self.asked.append(url)
        answer = self.routes.get(url, notFound)
        if isinstance(answer, Exception):
            raise answer
        if answer == notFound:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        if isinstance(answer, str):
            return FakeReply((fixtures / answer).read_bytes())
        return FakeReply(json.dumps(answer).encode("utf-8"))


def request(platform: Platform, ticker: str, title: str, side: Side = Side.yes) -> PriceRequest:
    return PriceRequest("w1", platform, side, title, ticker)


kalshiMarketUrl = f"{kalshiApi}/markets/SENATETX-26-R"
kalshiEventUrl = f"{kalshiApi}/events/SENATETX-26?with_nested_markets=true"
polymarketEventSlug = "arizona-governor-winner-2026"
polymarketMarketSlug = "will-the-republican-win-the-arizona-governor-race-in-2026"


def testLabelsMatchWholeWordsInOrder() -> None:
    assert labelInTitle("Ken Paxton", "Texas Senate winner? - Ken Paxton")
    assert labelInTitle("Andy Biggs (R)", "Andy Biggs (R) - Arizona Governor Election Winner")
    assert not labelInTitle("Other", "My brother's wager")  # not inside a word
    assert not labelInTitle("Party A", "Republican Party - U.S. House Midterm Winner")
    assert not labelInTitle("", "anything")


# -------------------------------------------------------------- Kalshi ----


def testAKalshiMarketTickerGivesItsBid() -> None:
    service = PriceService(FakeSite({kalshiMarketUrl: "kalshiMarket.json"}))

    yes = service.quote(request(Platform.kalshi, "senatetx-26-r", "Ken Paxton"))
    no = service.quote(request(Platform.kalshi, "SENATETX-26-R", "Ken Paxton", Side.no))

    market = json.loads((fixtures / "kalshiMarket.json").read_text())["market"]
    assert yes.price == pytest.approx(float(market["yes_bid_dollars"]))
    assert no.price == pytest.approx(float(market["no_bid_dollars"]))
    assert yes.ticker == "SENATETX-26-R"


def testAKalshiEventPicksTheCandidateFromTheTitle() -> None:
    service = PriceService(FakeSite({kalshiEventUrl: "kalshiEvent.json"}))

    title = "Texas Senate winner? - Ken Paxton"
    quote = service.quote(request(Platform.kalshi, "SENATETX-26", title))

    assert quote.ticker == "SENATETX-26-R"  # handed back, so next time is direct
    assert 0 < quote.price < 1


def testAKalshiEventWithOneMarketNeedsNoName() -> None:
    url = f"{kalshiApi}/events/KXIRANDEMOCRACY-27MAR01?with_nested_markets=true"
    service = PriceService(FakeSite({url: "kalshiIranEvent.json"}))

    quote = service.quote(request(Platform.kalshi, "KXIRANDEMOCRACY-27MAR01", "Iran?"))

    assert quote.ticker == "KXIRANDEMOCRACY-27MAR01-T6"


def testAKalshiEventWithNoMatchingNameListsTheChoices() -> None:
    service = PriceService(FakeSite({kalshiEventUrl: "kalshiEvent.json"}))
    update = service.updateAll([request(Platform.kalshi, "SENATETX-26", "Texas Senate winner?")])

    assert update.quotes == []
    reason = update.skipped[0].reason
    assert "Ken Paxton" in reason and "James Talarico" in reason


def testAKalshiSeriesIsRefusedRatherThanGuessed() -> None:
    service = PriceService(FakeSite({}))  # neither a market nor an event by that name
    update = service.updateAll([request(Platform.kalshi, "KXIRANDEMOCRACY", "Iran?")])

    assert update.quotes == []
    assert "series" in update.skipped[0].reason
    assert not update.skipped[0].unreachable


def testAClosedKalshiMarketSaysToSettle() -> None:
    closed = {"market": {"ticker": "X-1", "status": "finalized", "result": "yes",
                         "yes_bid_dollars": "0.0000", "no_bid_dollars": "0.0000"}}
    service = PriceService(FakeSite({f"{kalshiApi}/markets/X-1": closed}))
    update = service.updateAll([request(Platform.kalshi, "X-1", "t")])

    assert "settle this wager" in update.skipped[0].reason


def testNoBidIsNotAPriceOfZero() -> None:
    quiet = {"market": {"ticker": "X-1", "status": "active", "result": "",
                        "yes_bid_dollars": "0.0000", "no_bid_dollars": "0.9900"}}
    service = PriceService(FakeSite({f"{kalshiApi}/markets/X-1": quiet}))
    update = service.updateAll([request(Platform.kalshi, "X-1", "t")])

    assert update.quotes == []
    assert "nobody is bidding" in update.skipped[0].reason


# ---------------------------------------------------------- Polymarket ----


def testAPolymarketMarketSlugGivesTheYesBidOrOneMinusTheAsk() -> None:
    url = f"{polymarketApi}/markets?slug={polymarketMarketSlug}"
    service = PriceService(FakeSite({url: "polymarketMarket.json"}))

    yes = service.quote(request(Platform.polymarket, polymarketMarketSlug, "Andy Biggs (R)"))
    no = service.quote(request(Platform.polymarket, polymarketMarketSlug, "x", Side.no))

    market = json.loads((fixtures / "polymarketMarket.json").read_text())[0]
    assert yes.price == pytest.approx(market["bestBid"])
    assert no.price == pytest.approx(1 - market["bestAsk"])
    assert yes.ticker == polymarketMarketSlug


def testAPolymarketEventPicksTheCandidateAndIgnoresPlaceholders() -> None:
    routes = {
        f"{polymarketApi}/markets?slug={polymarketEventSlug}": [],
        f"{polymarketApi}/events?slug={polymarketEventSlug}": "polymarketEvent.json",
    }
    service = PriceService(FakeSite(routes))

    quote = service.quote(request(Platform.polymarket, polymarketEventSlug,
                                  "Andy Biggs (R) - Arizona Governor Election Winner"))

    assert quote.ticker == polymarketMarketSlug


def testAnUnknownPolymarketSlugSaysSo() -> None:
    routes = {f"{polymarketApi}/markets?slug=nope": [], f"{polymarketApi}/events?slug=nope": []}
    update = PriceService(FakeSite(routes)).updateAll([request(Platform.polymarket, "nope", "t")])

    assert "no market or event nope" in update.skipped[0].reason


# ------------------------------------------------------------ the run ----


def testEachUrlIsFetchedOnceARun() -> None:
    """Three wagers on one race cost one request, not three."""
    site = FakeSite({kalshiEventUrl: "kalshiEvent.json"})
    service = PriceService(site)
    requests = [
        PriceRequest(f"w{i}", Platform.kalshi, Side.yes, "Ken Paxton", "SENATETX-26")
        for i in range(3)
    ]

    update = service.updateAll(requests)

    assert len(update.quotes) == 3
    assert site.asked.count(kalshiEventUrl) == 1


def testWagersWithoutATickerAreSkippedWithAHint() -> None:
    update = PriceService(FakeSite({})).updateAll([request(Platform.kalshi, "", "t")])

    assert "paste the market's address" in update.skipped[0].reason
    assert not update.nothingReached  # nothing was even tried


def testNoConnectionIsToldApartFromABadTicker() -> None:
    site = FakeSite({kalshiMarketUrl: urllib.error.URLError("getaddrinfo failed")})
    update = PriceService(site).updateAll([request(Platform.kalshi, "SENATETX-26-R", "t")])

    assert update.skipped[0].unreachable
    assert "could not reach api.elections.kalshi.com" in update.skipped[0].reason
    assert update.nothingReached


def testTheUpdateTimeIsTheRunsOwn() -> None:
    moment = datetime(2026, 10, 16, 9, 42)
    update = PriceService(FakeSite({})).updateAll([], now=moment)

    assert update.at == moment


# ------------------------------------------------------- into the book ----


def testApplyingPricesSetsPriceTickerAndTimeInOneWrite(tmp_path) -> None:
    store = WagerStore(tmp_path / "wagers.json")
    openOne = Wager(title="Ken Paxton", stake=10.0, price=0.4, ticker="SENATETX-26")
    closedOne = Wager(title="Done", stake=1.0, price=0.5, status=Status.won, payout=2.0)
    store.addMany([openOne, closedOne])
    moment = datetime(2026, 10, 16, 9, 42)

    changed = store.applyPrices(
        [(openOne.id, 0.38, "SENATETX-26-R"), (closedOne.id, 0.9, "X"), ("gone", 0.5, "Y")],
        moment,
    )

    assert changed == 1
    reopened = WagerStore(store.path)
    reopened.load()
    priced = reopened.find(openOne.id)
    assert priced.currentPrice == 0.38
    assert priced.ticker == "SENATETX-26-R"
    assert priced.pricedAt == moment
    assert reopened.find(closedOne.id).currentPrice is None
