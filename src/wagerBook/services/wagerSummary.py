"""Totals over a set of wagers, for the line under each table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from wagerBook.models.wager import Status, Wager


@dataclass(frozen=True)
class ActiveSummary:
    count: int = 0
    staked: float = 0.0
    fees: float = 0.0
    maxPayout: float = 0.0
    """What comes back if every open wager wins."""
    maxProfit: float = 0.0
    priced: int = 0
    """Open wagers with a current price; the next three cover only these."""
    value: float = 0.0
    """What the priced wagers could be sold for now."""
    unrealized: float = 0.0
    """That value less what the priced wagers cost, fees included."""
    fetched: int = 0
    """Of the priced, how many came from Update Prices - the rest were typed in."""
    oldestPrice: datetime | None = None
    """The stalest fetched price: the totals are no fresher than this."""


@dataclass(frozen=True)
class ClosedSummary:
    count: int = 0
    won: int = 0
    lost: int = 0
    sold: int = 0
    voided: int = 0
    staked: float = 0.0
    fees: float = 0.0
    returned: float = 0.0
    """Everything that came back, payouts and refunds alike."""
    profit: float = 0.0

    @property
    def decided(self) -> int:
        """Wagers the market actually decided; sold and voided are neither."""
        return self.won + self.lost

    @property
    def winRate(self) -> float | None:
        return self.won / self.decided if self.decided else None


def summarizeActive(wagers: list[Wager]) -> ActiveSummary:
    openOnes = [wager for wager in wagers if wager.isActive]
    priced = [wager for wager in openOnes if wager.markValue is not None]
    moments = [wager.pricedAt for wager in priced if wager.pricedAt is not None]
    return ActiveSummary(
        count=len(openOnes),
        staked=sum(wager.stake for wager in openOnes),
        fees=sum(wager.fees for wager in openOnes),
        maxPayout=sum(wager.maxPayout for wager in openOnes),
        maxProfit=sum(wager.maxProfit for wager in openOnes),
        priced=len(priced),
        value=sum(wager.markValue or 0.0 for wager in priced),
        unrealized=sum((wager.markValue or 0.0) - wager.stake - wager.fees for wager in priced),
        fetched=len(moments),
        oldestPrice=min(moments) if moments else None,
    )


def summarizeClosed(wagers: list[Wager]) -> ClosedSummary:
    done = [wager for wager in wagers if wager.isClosed]
    counts = dict.fromkeys(Status, 0)
    for wager in done:
        counts[wager.status] += 1
    return ClosedSummary(
        count=len(done),
        won=counts[Status.won],
        lost=counts[Status.lost],
        sold=counts[Status.sold],
        voided=counts[Status.voided],
        staked=sum(wager.stake for wager in done),
        fees=sum(wager.fees for wager in done),
        returned=sum(wager.payout or 0.0 for wager in done),
        profit=sum(wager.realizedProfit or 0.0 for wager in done),
    )
