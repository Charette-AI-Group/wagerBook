"""Tests for the totals under each table."""

from __future__ import annotations

import pytest

from wagerBook.models.wager import Status, Wager
from wagerBook.services.wagerSummary import summarizeActive, summarizeClosed


def closed(title: str, status: Status, stake: float, price: float, payout: float) -> Wager:
    return Wager(title=title, stake=stake, price=price, status=status, payout=payout)


def testActiveTotalsIgnoreClosedWagers() -> None:
    wagers = [
        Wager(title="A", stake=10.0, price=0.5, fees=0.1),
        Wager(title="B", stake=30.0, price=0.75, fees=0.2),
        closed("C", Status.won, 5.0, 0.5, 10.0),
    ]

    summary = summarizeActive(wagers)

    assert summary.count == 2
    assert summary.staked == pytest.approx(40.0)
    assert summary.fees == pytest.approx(0.3)
    assert summary.maxPayout == pytest.approx(20.0 + 40.0)
    assert summary.maxProfit == pytest.approx(60.0 - 40.0 - 0.3)


def testClosedTotalsCountEachOutcome() -> None:
    wagers = [
        Wager(title="Open", stake=10.0, price=0.5),
        closed("W", Status.won, 10.0, 0.5, 20.0),
        closed("W2", Status.won, 10.0, 0.25, 40.0),
        closed("L", Status.lost, 10.0, 0.5, 0.0),
        closed("S", Status.sold, 10.0, 0.5, 12.0),
        closed("V", Status.voided, 10.0, 0.5, 10.0),
    ]

    summary = summarizeClosed(wagers)

    assert summary.count == 5
    assert (summary.won, summary.lost, summary.sold, summary.voided) == (2, 1, 1, 1)
    assert summary.staked == pytest.approx(50.0)
    assert summary.returned == pytest.approx(82.0)
    assert summary.profit == pytest.approx(32.0)
    # Only the market's own decisions count toward the hit rate.
    assert summary.decided == 3
    assert summary.winRate == pytest.approx(2 / 3)


def testWinRateIsUndefinedWithNothingDecided() -> None:
    summary = summarizeClosed([closed("S", Status.sold, 10.0, 0.5, 12.0)])

    assert summary.winRate is None


def testEmptyBook() -> None:
    assert summarizeActive([]).count == 0
    assert summarizeClosed([]).profit == 0.0
