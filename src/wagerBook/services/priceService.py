"""Today's sell price for each open wager, from the sites' public market data.

Both sites publish prices without a login or key:

  Kalshi      https://api.elections.kalshi.com/trade-api/v2
              /markets/{ticker}                        one market
              /events/{ticker}?with_nested_markets=true an event and its markets
              price fields: yes_bid_dollars, no_bid_dollars ("0.3800")
  Polymarket US (the CFTC exchange US accounts trade on), tried first
              https://gateway.polymarket.us
              /v1/market/slug/{slug}                   one market
              /v1/events/slug/{slug}                   an event and its markets
              price fields: bestBidQuote, bestAskQuote ({"value": "0.4400"})
              ids look like usse-me-2026-11-03 (event), ewc-usse-me-...-rep
  Polymarket  https://gamma-api.polymarket.com - polymarket.com, when the US
              exchange has no such id
              /markets?slug={slug}                     one market, in a list
              /events?slug={slug}                      an event and its markets
              price fields: bestBid, bestAsk (for Yes, as numbers)

The two Polymarkets are separate exchanges with separate prices, so a wager
is priced on the one its id belongs to. Each answers 404 for the other's ids.

The price taken is what the position could be sold for now - the best bid
for the side held - which is what Kalshi's Cash Out shows. It never flatters
a position the way the last trade or the ask can. On Polymarket only the Yes
book is quoted, so a No holder's bid is one minus the Yes ask.

A ticker can name an event rather than one market: the address of "Texas
Senate winner?" names the race, and Ken Paxton is one market inside it. The
market is then picked by its label - "Ken Paxton", "Andy Biggs (R)" - found
as whole words in the wager's title, and that market's own id is handed back
so the wager points straight at it next time. Failing that, a label whose
first and last names are both in the title will do, so "Susan M Collins"
still finds "Susan Collins (R)". When no label or more than one matches, the
wager is skipped with the choices listed: guessing a price is worse than not
having one.

No Qt here; the worker runs this off the interface thread.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from wagerBook.models.wager import Platform, Side, Wager

logger = logging.getLogger(__name__)

kalshiApi = "https://api.elections.kalshi.com/trade-api/v2"
polymarketApi = "https://gamma-api.polymarket.com"
polymarketUsApi = "https://gateway.polymarket.us"
polymarketUsOpen = "MARKET_STATUS_OPEN"
requestTimeoutSeconds = 10.0
userAgent = "WagerBook/0.1 (desktop app)"

kalshiClosedStatuses = {"closed", "settled", "finalized", "determined"}


class PriceLookupError(Exception):
    """This wager could not be priced; the message says why, for the reader."""


class SiteUnreachableError(PriceLookupError):
    """The site did not answer at all - a network problem, not a bad ticker."""


@dataclass(frozen=True)
class PriceRequest:
    """What the worker needs from a wager, copied so no thread shares the book."""

    wagerId: str
    platform: Platform
    side: Side
    title: str
    ticker: str

    @classmethod
    def fromWager(cls, wager: Wager) -> PriceRequest:
        return cls(wager.id, wager.platform, wager.side, wager.title, wager.ticker.strip())


@dataclass(frozen=True)
class PriceQuote:
    wagerId: str
    price: float
    """What the side held could be sold for now, 0 to 1."""
    ticker: str
    """The market's own id: the event's ticker is replaced by the market picked."""


@dataclass(frozen=True)
class SkippedPrice:
    request: PriceRequest
    reason: str
    unreachable: bool = False


@dataclass
class PriceUpdate:
    at: datetime
    quotes: list[PriceQuote] = field(default_factory=list)
    skipped: list[SkippedPrice] = field(default_factory=list)

    @property
    def nothingReached(self) -> bool:
        """Every wager that was looked up failed for want of a connection."""
        tried = [skip for skip in self.skipped if skip.request.ticker]
        return not self.quotes and bool(tried) and all(skip.unreachable for skip in tried)


# ------------------------------------------------------------- matching ----


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def labelInTitle(label: str, title: str) -> bool:
    """The label's words, in order and whole, somewhere in the title."""
    labelWords, titleWords = words(label), words(title)
    if not labelWords:
        return False
    span = len(labelWords)
    return any(titleWords[i:i + span] == labelWords for i in range(len(titleWords) - span + 1))


def namesInTitle(label: str, title: str) -> bool:
    """The label's first and last names, whole, in the title; initials and middle names aside.

    The second try, for "Susan M Collins" against "Susan Collins (R)". A label of
    fewer than two real words never matches this way - "Party A" must not match
    every title with "party" in it.
    """
    names = [word for word in words(label) if len(word) > 1]
    if len(names) < 2:
        return False
    titleWords = set(words(title))
    return names[0] in titleWords and names[-1] in titleWords


def pickMarket(markets: list[dict], labelOf: Callable[[dict], str], title: str, what: str) -> dict:
    if len(markets) == 1:
        return markets[0]
    matches = [market for market in markets if labelInTitle(labelOf(market), title)]
    if not matches:
        matches = [market for market in markets if namesInTitle(labelOf(market), title)]
    if len(matches) > 1:
        # "Ken Paxton" beats a stray "Paxton": the longest label that fits wins, if alone.
        longest = max(len(words(labelOf(market))) for market in matches)
        matches = [market for market in matches if len(words(labelOf(market))) == longest]
    if len(matches) == 1:
        return matches[0]
    labels = ", ".join(label for label in (labelOf(market) for market in markets) if label)
    if not matches:
        raise PriceLookupError(
            f"{what} has several markets and none of their names is in the title. "
            f"Put one of these in the title, or the market's own address in Ticker: {labels}"
        )
    raise PriceLookupError(f"{what} has more than one market matching the title: {labels}")


def quoteValue(quote: object) -> object:
    """Polymarket US wraps prices: {"value": "0.4400", "currency": "USD"}."""
    return quote.get("value") if isinstance(quote, dict) else None


def bidPrice(value: object, what: str) -> float:
    try:
        price = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise PriceLookupError(f"{what} has no price quoted") from exc
    if price <= 0.0:
        raise PriceLookupError(f"nobody is bidding on {what} right now")
    return min(price, 1.0)


# -------------------------------------------------------------- service ----


Opener = Callable[..., object]


class PriceService:
    def __init__(self, opener: Opener = urllib.request.urlopen) -> None:
        self.opener = opener
        self.cache: dict[str, object | None] = {}

    def getJson(self, url: str) -> object | None:
        """The reply as JSON, or None for "no such thing" (404). One fetch per URL per run."""
        if url in self.cache:
            return self.cache[url]
        request = urllib.request.Request(url, headers={"User-Agent": userAgent,
                                                       "Accept": "application/json"})
        site = urllib.parse.urlparse(url).netloc
        try:
            with self.opener(request, timeout=requestTimeoutSeconds) as reply:  # type: ignore[attr-defined]
                data = json.loads(reply.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                data = None
            else:
                raise PriceLookupError(f"{site} answered with an error ({exc.code})") from exc
        except (OSError, ValueError) as exc:
            # URLError and timeouts are OSError; a garbled reply is a ValueError.
            raise SiteUnreachableError(f"could not reach {site}: {exc}") from exc
        self.cache[url] = data
        return data

    # ------------------------------------------------------------ Kalshi ----

    def kalshiQuote(self, request: PriceRequest) -> PriceQuote:
        ticker = urllib.parse.quote(request.ticker.upper(), safe="-.")
        found = self.getJson(f"{kalshiApi}/markets/{ticker}")
        if isinstance(found, dict) and isinstance(found.get("market"), dict):
            market = found["market"]
        else:
            event = self.getJson(f"{kalshiApi}/events/{ticker}?with_nested_markets=true")
            if not isinstance(event, dict) or not isinstance(event.get("event"), dict):
                raise PriceLookupError(
                    f"Kalshi has no market or event {request.ticker.upper()}. If it is a "
                    "series, paste the address of the market itself"
                )
            markets = event["event"].get("markets") or event.get("markets") or []
            if not markets:
                raise PriceLookupError(f"Kalshi event {request.ticker.upper()} has no markets")
            market = pickMarket(markets, lambda m: m.get("yes_sub_title") or "",
                                request.title, f"Kalshi event {request.ticker.upper()}")
        name = market.get("ticker") or request.ticker.upper()
        if market.get("result") or str(market.get("status", "")).lower() in kalshiClosedStatuses:
            raise PriceLookupError(f"Kalshi market {name} has closed; settle this wager")
        bidField = "yes_bid_dollars" if request.side == Side.yes else "no_bid_dollars"
        price = bidPrice(market.get(bidField), f"Kalshi market {name}")
        return PriceQuote(request.wagerId, price, name)

    # -------------------------------------------------------- Polymarket ----

    def polymarketUsMarket(self, request: PriceRequest) -> dict | None:
        """The market on Polymarket US, or None when the id is not one of its own."""
        slug = urllib.parse.quote(request.ticker, safe="")
        found = self.getJson(f"{polymarketUsApi}/v1/market/slug/{slug}")
        if isinstance(found, dict) and isinstance(found.get("market"), dict):
            return found["market"]
        event = self.getJson(f"{polymarketUsApi}/v1/events/slug/{slug}")
        if not isinstance(event, dict) or not isinstance(event.get("event"), dict):
            return None
        markets = event["event"].get("markets") or []
        if not markets:
            raise PriceLookupError(f"Polymarket event {request.ticker} has no markets")
        return pickMarket(markets, lambda m: m.get("title") or m.get("titleShort") or "",
                          request.title, f"Polymarket event {request.ticker}")

    def polymarketComMarket(self, request: PriceRequest) -> dict:
        """The market on polymarket.com; the last place a Polymarket id can be."""
        slug = urllib.parse.quote(request.ticker, safe="")
        found = self.getJson(f"{polymarketApi}/markets?slug={slug}")
        if isinstance(found, list) and found:
            return found[0]
        events = self.getJson(f"{polymarketApi}/events?slug={slug}")
        if not isinstance(events, list) or not events:
            raise PriceLookupError(f"Polymarket has no market or event {request.ticker}")
        markets = events[0].get("markets") or []
        if not markets:
            raise PriceLookupError(f"Polymarket event {request.ticker} has no markets")
        return pickMarket(markets, lambda m: m.get("groupItemTitle") or "",
                          request.title, f"Polymarket event {request.ticker}")

    def polymarketQuote(self, request: PriceRequest) -> PriceQuote:
        market = self.polymarketUsMarket(request)
        if market is not None:
            status = market.get("status")
            closed = bool(market.get("closed")) or (bool(status) and status != polymarketUsOpen)
            bid = quoteValue(market.get("bestBidQuote"))
            ask = quoteValue(market.get("bestAskQuote"))
        else:
            market = self.polymarketComMarket(request)
            closed = bool(market.get("closed"))
            bid, ask = market.get("bestBid"), market.get("bestAsk")
        name = market.get("slug") or request.ticker
        if closed:
            raise PriceLookupError(f"Polymarket market {name} has closed; settle this wager")
        what = f"Polymarket market {name}"
        if request.side == Side.yes:
            price = bidPrice(bid, what)
        else:
            # Only the Yes book is quoted: selling No is meeting the best Yes ask.
            if ask is None:
                raise PriceLookupError(f"{what} has no price quoted")
            price = bidPrice(1.0 - float(ask), what)  # type: ignore[arg-type]
        return PriceQuote(request.wagerId, round(price, 6), name)

    # ---------------------------------------------------------- the lot ----

    def quote(self, request: PriceRequest) -> PriceQuote:
        if request.platform == Platform.kalshi:
            return self.kalshiQuote(request)
        return self.polymarketQuote(request)

    def updateAll(self, requests: list[PriceRequest], now: datetime | None = None) -> PriceUpdate:
        update = PriceUpdate(at=now or datetime.now().replace(microsecond=0))
        for request in requests:
            if not request.ticker:
                update.skipped.append(SkippedPrice(
                    request, "no ticker: paste the market's address into Ticker"))
                continue
            try:
                update.quotes.append(self.quote(request))
            except SiteUnreachableError as exc:
                update.skipped.append(SkippedPrice(request, str(exc), unreachable=True))
            except PriceLookupError as exc:
                update.skipped.append(SkippedPrice(request, str(exc)))
        logger.info("Priced %d wagers, skipped %d", len(update.quotes), len(update.skipped))
        return update
