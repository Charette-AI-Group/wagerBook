"""Tests for the add/edit dialog."""

from __future__ import annotations

from datetime import date

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


def testAcceptWithAValidFormAccepts(qtbot) -> None:
    dialog = WagerDialog()
    qtbot.addWidget(dialog)
    dialog.titleEdit.setText("Something")
    dialog.stakeSpin.setValue(5.0)

    dialog.accept()

    assert dialog.result() == dialog.DialogCode.Accepted
