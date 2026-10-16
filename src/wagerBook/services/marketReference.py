"""Turn what was pasted into the Ticker box into the id each site's API uses.

People copy a market's web address, not its ticker, so both are accepted:

  https://kalshi.com/markets/senatetx/texas-senate-winner/senatetx-26
      -> Kalshi, SENATETX-26 (the event; the candidate is picked at update time)
  https://polymarket.com/event/arizona-governor-winner-2026
      -> Polymarket, arizona-governor-winner-2026 (an event slug)
  https://polymarket.com/event/arizona-governor-winner-2026/will-the-republican-...
      -> Polymarket, the market slug after the event
  SENATETX-26-R, will-the-republican-win-...
      -> kept as typed; the platform is whatever the wager says

A Kalshi address that stops at the series (/markets/senatetx) is returned as
the series ticker. The price service then refuses it rather than choosing an
event inside the series, which could be the wrong one.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from wagerBook.models.wager import Platform


@dataclass(frozen=True)
class MarketReference:
    platform: Platform | None
    """None when a bare id was typed: the wager's own platform applies."""
    identifier: str


def looksLikeAddress(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered.startswith(("http://", "https://", "www.")) or any(
        host in lowered for host in ("kalshi.com/", "polymarket.com/", "polymarket.us/")
    )


def pathParts(address: str) -> tuple[str, list[str]]:
    text = address.strip()
    if "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    host = parsed.netloc.lower().removeprefix("www.")
    return host, [part for part in parsed.path.split("/") if part]


def kalshiIdentifier(parts: list[str]) -> str | None:
    """/markets/{series}/{slug}/{event} - the event ticker, else the series."""
    if parts and parts[0].lower() in ("markets", "events"):
        parts = parts[1:]
    if not parts:
        return None
    chosen = parts[2] if len(parts) >= 3 else parts[0]
    return chosen.upper()


def polymarketIdentifier(parts: list[str]) -> str | None:
    """/event/{event}[/{market}] or /market/{market}: the most specific slug."""
    for index, part in enumerate(parts):
        if part.lower() in ("event", "market", "markets") and index + 1 < len(parts):
            return parts[-1] if part.lower() == "event" else parts[index + 1]
    return parts[-1] if parts else None


def parseMarketReference(text: str) -> MarketReference | None:
    """None for an empty box or an address that names no market."""
    stripped = text.strip()
    if not stripped:
        return None
    if not looksLikeAddress(stripped):
        return MarketReference(None, stripped)
    host, parts = pathParts(stripped)
    if host.endswith("kalshi.com"):
        identifier = kalshiIdentifier(parts)
        return MarketReference(Platform.kalshi, identifier) if identifier else None
    if "polymarket" in host:
        identifier = polymarketIdentifier(parts)
        return MarketReference(Platform.polymarket, identifier) if identifier else None
    return None
