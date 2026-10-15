"""Tests for the settle dialog."""

from __future__ import annotations

from datetime import date

import pytest
from PySide6.QtCore import QDate

from wagerBook.models.wager import Status, Wager
from wagerBook.ui.dialogs.settleDialog import SettleDialog


def openWager() -> Wager:
    return Wager(title="Rain", stake=20.0, price=0.25, fees=0.3, currentPrice=0.6)


def testOutcomesOfferedAreTheClosedOnes(qtbot) -> None:
    dialog = SettleDialog(None, openWager())
    qtbot.addWidget(dialog)

    offered = [dialog.outcomeBox.itemText(i) for i in range(dialog.outcomeBox.count())]

    assert offered == ["Won", "Lost", "Sold", "Voided"]
    assert "Active" not in offered


def testEachOutcomeFillsInItsUsualPayout(qtbot) -> None:
    dialog = SettleDialog(None, openWager())
    qtbot.addWidget(dialog)

    assert dialog.status() == Status.won
    assert dialog.payoutSpin.value() == pytest.approx(80.0)
    assert dialog.resultLabel.text() == "+$59.70"

    dialog.outcomeBox.setCurrentText("Lost")
    assert dialog.payoutSpin.value() == 0.0
    assert dialog.resultLabel.text() == "-$20.30"

    dialog.outcomeBox.setCurrentText("Voided")
    assert dialog.payoutSpin.value() == pytest.approx(20.0)
    assert dialog.resultLabel.text() == "-$0.30"

    dialog.outcomeBox.setCurrentText("Sold")
    assert dialog.payoutSpin.value() == pytest.approx(48.0)


def testThePayoutStaysEditable(qtbot) -> None:
    dialog = SettleDialog(None, openWager())
    qtbot.addWidget(dialog)
    dialog.outcomeBox.setCurrentText("Sold")
    dialog.payoutSpin.setValue(30.0)
    dialog.settledEdit.setDate(QDate(2026, 10, 7))

    assert dialog.settlement() == (Status.sold, 30.0, date(2026, 10, 7))
    assert dialog.resultLabel.text() == "+$9.70"
