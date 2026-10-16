"""Tests for the wager arithmetic and its on-disk shape."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from wagerBook.models.wager import Platform, Side, Status, Wager


def testContractsPayoutAndProfitFollowFromStakeAndPrice() -> None:
    """$25 at 40 cents buys 62.5 contracts, each worth $1 if right."""
    wager = Wager(title="Rain tomorrow", stake=25.0, price=0.40, fees=0.50)

    assert wager.contracts == pytest.approx(62.5)
    assert wager.maxPayout == pytest.approx(62.5)
    assert wager.maxProfit == pytest.approx(62.5 - 25.0 - 0.50)
    assert wager.maxReturn == pytest.approx((62.5 - 25.5) / 25.0)


def testTheNoSideUsesItsOwnPrice() -> None:
    """Buying No at 70 cents is a 70% market chance, not 30%."""
    wager = Wager(title="Fed cuts in June", side=Side.no, stake=70.0, price=0.70)

    assert wager.contracts == pytest.approx(100.0)
    assert wager.maxProfit == pytest.approx(30.0)


def testAZeroPriceCannotDivide() -> None:
    wager = Wager(title="Broken", stake=10.0, price=0.0)

    assert wager.contracts == 0.0
    assert wager.maxReturn == pytest.approx(-1.0)


def testMarkValueNeedsACurrentPrice() -> None:
    wager = Wager(title="Open", stake=50.0, price=0.50)
    assert wager.markValue is None

    wager.currentPrice = 0.65
    assert wager.markValue == pytest.approx(65.0)


def testRealizedProfitOnlyOnceClosed() -> None:
    wager = Wager(title="Open", stake=20.0, price=0.25, fees=0.30)
    assert wager.realizedProfit is None
    assert wager.isActive and not wager.isClosed

    wager.status = Status.won
    wager.payout = 80.0
    assert wager.realizedProfit == pytest.approx(80.0 - 20.0 - 0.30)
    assert wager.isClosed and not wager.isActive

    wager.status = Status.lost
    wager.payout = 0.0
    assert wager.realizedProfit == pytest.approx(-20.30)


def testExpectedPayoutByOutcome() -> None:
    wager = Wager(title="Open", stake=20.0, price=0.25, currentPrice=0.60)

    assert wager.expectedPayout(Status.won) == pytest.approx(80.0)
    assert wager.expectedPayout(Status.lost) == 0.0
    assert wager.expectedPayout(Status.voided) == pytest.approx(20.0)
    # Selling early is worth whatever the position is marked at.
    assert wager.expectedPayout(Status.sold) == pytest.approx(48.0)
    wager.currentPrice = None
    assert wager.expectedPayout(Status.sold) == 0.0


def testDictRoundTripKeepsEverything() -> None:
    wager = Wager(
        title="Chiefs win the Super Bowl",
        platform=Platform.polymarket,
        side=Side.yes,
        stake=100.0,
        price=0.18,
        fees=1.25,
        placedOn=date(2026, 9, 1),
        closesOn=date(2027, 2, 14),
        category="Sports",
        ticker="chiefs-sb-2027",
        notes="Bought on the dip",
        currentPrice=0.22,
        pricedAt=datetime(2026, 10, 16, 9, 42, 5),
        status=Status.active,
    )

    rebuilt = Wager.fromDict(wager.toDict())

    assert rebuilt == wager


def testSettledFieldsRoundTripToo() -> None:
    wager = Wager(
        title="Done", status=Status.won, payout=40.0, settledOn=date(2026, 10, 1)
    )

    rebuilt = Wager.fromDict(wager.toDict())

    assert rebuilt.status == Status.won
    assert rebuilt.payout == 40.0
    assert rebuilt.settledOn == date(2026, 10, 1)


def testMissingOptionalKeysGetDefaults() -> None:
    """An older or hand-edited file should still load."""
    rebuilt = Wager.fromDict({"title": "Sparse", "stake": "5", "price": "0.5"})

    assert rebuilt.title == "Sparse"
    assert rebuilt.stake == 5.0
    assert rebuilt.platform == Platform.kalshi
    assert rebuilt.status == Status.active
    assert rebuilt.closesOn is None
    assert rebuilt.id
