"""Tests for the add/edit dialog."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from PySide6.QtCore import QDate

from wagerBook.models.wager import Platform, Side, Status, Wager
from wagerBook.ui.dialogs.wagerDialog import WagerDialog


def testANewWagerStartsActiveToday(qtbot) -> None:
    dialog = WagerDialog()
    qtbot.addWidget(dialog)

    dialog.titleEdit.setText("Rain tomorrow")
    dialog.stakeSpin.setValue(25.0)
    dialog.priceSpin.setValue(40.0)
    wager = dialog.wager()

    assert wager.title == "Rain tomorrow"
    assert wager.status == Status.active
    assert wager.placedOn == date.today()
    assert wager.price == pytest.approx(0.40)
    assert wager.stake == 25.0
    assert wager.closesOn is None and wager.currentPrice is None
    assert wager.platform == Platform.kalshi and wager.side == Side.yes


def testEveryFieldRoundTripsThroughTheForm(qtbot) -> None:
    original = Wager(
        title="Chiefs win",
        platform=Platform.polymarket,
        side=Side.no,
        stake=100.0,
        price=0.18,
        fees=1.25,
        placedOn=date(2026, 9, 1),
        closesOn=date(2027, 2, 14),
        category="Sports",
        ticker="chiefs-sb",
        notes="Bought on the dip",
        currentPrice=0.22,
        status=Status.won,
        payout=550.0,
        settledOn=date(2027, 2, 15),
    )
    dialog = WagerDialog(wager=original)
    qtbot.addWidget(dialog)

    rebuilt = dialog.wager()

    assert rebuilt.id == original.id
    assert rebuilt.toDict() == original.toDict()
    assert dialog.windowTitle() == "Edit Wager"


def testOptionalDatesAndPricesFollowTheirCheckboxes(qtbot) -> None:
    dialog = WagerDialog()
    qtbot.addWidget(dialog)
    dialog.titleEdit.setText("Later")
    dialog.closesCheck.setChecked(True)
    dialog.closesEdit.setDate(QDate(2026, 12, 31))
    dialog.currentCheck.setChecked(True)
    dialog.currentSpin.setValue(61.5)

    wager = dialog.wager()

    assert wager.closesOn == date(2026, 12, 31)
    assert wager.currentPrice == pytest.approx(0.615)
    assert dialog.closesEdit.isEnabled() and dialog.currentSpin.isEnabled()


def testTheSummaryLineFollowsTheNumbers(qtbot) -> None:
    dialog = WagerDialog()
    qtbot.addWidget(dialog)

    dialog.stakeSpin.setValue(25.0)
    dialog.priceSpin.setValue(40.0)
    dialog.feesSpin.setValue(0.5)

    assert "Contracts 62.50" in dialog.summaryLabel.text()
    assert "Max win $62.50" in dialog.summaryLabel.text()
    assert "Profit if won +$37.00 (+148%)" in dialog.summaryLabel.text()


def testAcceptRefusesAnEmptyTitleAndSaysWhy(qtbot) -> None:
    dialog = WagerDialog()
    qtbot.addWidget(dialog)
    dialog.stakeSpin.setValue(5.0)

    dialog.accept()

    assert dialog.result() != dialog.DialogCode.Accepted
    assert dialog.problemLabel.isVisibleTo(dialog)
    assert "title" in dialog.problemLabel.text()


def testAcceptRefusesAZeroStake(qtbot) -> None:
    dialog = WagerDialog()
    qtbot.addWidget(dialog)
    dialog.titleEdit.setText("Something")

    dialog.accept()

    assert dialog.result() != dialog.DialogCode.Accepted
    assert "stake" in dialog.problemLabel.text()


def testAPastedKalshiAddressBecomesItsTickerAndPlatform(qtbot) -> None:
    dialog = WagerDialog()
    qtbot.addWidget(dialog)
    dialog.platformBox.setCurrentText("Polymarket")

    dialog.tickerEdit.setText(
        "https://kalshi.com/markets/senatetx/texas-senate-winner/senatetx-26"
    )
    dialog.readTickerAddress()

    assert dialog.tickerEdit.text() == "SENATETX-26"
    assert dialog.platformBox.currentText() == "Kalshi"
    assert "Kalshi address" in dialog.tickerNote.text()


def testAPastedPolymarketAddressIsReadOnOk(qtbot) -> None:
    """Paste, then OK straight away: the address is still read."""
    dialog = WagerDialog()
    qtbot.addWidget(dialog)
    dialog.titleEdit.setText("Andy Biggs (R)")
    dialog.stakeSpin.setValue(9.85)
    dialog.tickerEdit.setText("https://polymarket.com/event/arizona-governor-winner-2026")

    dialog.accept()

    wager = dialog.wager()
    assert wager.ticker == "arizona-governor-winner-2026"
    assert wager.platform == Platform.polymarket


def testAnAddressFromElsewhereIsLeftAndExplained(qtbot) -> None:
    dialog = WagerDialog()
    qtbot.addWidget(dialog)
    dialog.tickerEdit.setText("https://example.com/some/page")

    dialog.readTickerAddress()

    assert dialog.tickerEdit.text() == "https://example.com/some/page"
    assert "not a Kalshi or Polymarket market" in dialog.tickerNote.text()


def testAPlainTickerIsLeftAlone(qtbot) -> None:
    dialog = WagerDialog()
    qtbot.addWidget(dialog)
    dialog.tickerEdit.setText("SENATETX-26-R")

    dialog.readTickerAddress()

    assert dialog.tickerEdit.text() == "SENATETX-26-R"
    assert not dialog.tickerNote.isVisibleTo(dialog)


def testUntouchedPricesKeepEveryDigitAndTheirTime(qtbot) -> None:
    """The form shows a tenth of a percent; OK on an untouched form must not round."""
    fetched = datetime(2026, 10, 16, 9, 42)
    original = Wager(title="Paxton", stake=9.99, price=0.396271, currentPrice=0.3825,
                     pricedAt=fetched)
    dialog = WagerDialog(wager=original)
    qtbot.addWidget(dialog)

    wager = dialog.wager()

    assert wager.price == 0.396271
    assert wager.maxPayout == pytest.approx(original.maxPayout)
    assert wager.currentPrice == 0.3825
    assert wager.pricedAt == fetched


def testPricesTakeThousandthsOfAPercent(qtbot) -> None:
    """Kalshi's 11.69 cent average is 11.685% unrounded; the form holds that."""
    dialog = WagerDialog()
    qtbot.addWidget(dialog)

    dialog.priceSpin.setValue(11.685)
    dialog.currentSpin.setValue(9.9)

    assert dialog.priceSpin.decimals() == 3
    assert dialog.priceSpin.text().startswith("11.685")
    assert dialog.wager().price == pytest.approx(0.11685)
    dialog.priceSpin.setValue(0.001)
    assert dialog.priceSpin.value() == pytest.approx(0.001)  # the smallest it takes


def testAnExactPriceSurvivesAnUntouchedOk(qtbot) -> None:
    """99.99 over 855.72 contracts is 11.6849...%: shown as 11.685, kept exact."""
    original = Wager(title="Republicans sweep", stake=99.99, price=99.99 / 855.72)
    dialog = WagerDialog(wager=original)
    qtbot.addWidget(dialog)

    assert dialog.priceSpin.text().startswith("11.685")
    assert dialog.wager().price == original.price
    assert dialog.wager().maxPayout == pytest.approx(855.72)


def testATypedCurrentPriceCountsAsEnteredByHand(qtbot) -> None:
    original = Wager(title="Paxton", stake=10.0, price=0.4, currentPrice=0.38,
                     pricedAt=datetime(2026, 10, 16, 9, 42))
    dialog = WagerDialog(wager=original)
    qtbot.addWidget(dialog)

    dialog.currentSpin.setValue(41.0)
    wager = dialog.wager()

    assert wager.currentPrice == pytest.approx(0.41)
    assert wager.pricedAt is None


def testAcceptWithAValidFormAccepts(qtbot) -> None:
    dialog = WagerDialog()
    qtbot.addWidget(dialog)
    dialog.titleEdit.setText("Something")
    dialog.stakeSpin.setValue(5.0)

    dialog.accept()

    assert dialog.result() == dialog.DialogCode.Accepted
