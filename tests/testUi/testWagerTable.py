"""Tests for the table model, its formatting, and sorting by real values."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt

from wagerBook.models.wager import Side, Status, Wager
from wagerBook.ui.wagers.wagerColumns import (
    activeColumns,
    closedColumns,
    money,
    percent,
    signedMoney,
    signedPercent,
)
from wagerBook.ui.wagers.wagerTable import WagerTable
from wagerBook.ui.wagers.wagerTableModel import gainColour, lossColour, sortRole


def testMoneyAndPercentFormatting() -> None:
    assert money(1234.5) == "$1,234.50"
    assert money(-3.0) == "-$3.00"
    assert money(None) == ""
    assert signedMoney(12.0) == "+$12.00"
    assert signedMoney(-12.0) == "-$12.00"
    assert signedMoney(0.0) == "$0.00"
    assert percent(0.425) == "42.5%"
    assert signedPercent(0.6) == "+60%"
    assert signedPercent(-0.25) == "-25%"


def columnTexts(table: WagerTable, row: int) -> dict[str, str]:
    index = table.proxy.index(row, 0)
    wager = table.wagerAtProxyIndex(index)
    assert wager is not None
    return {column.title: column.text(wager) for column in table.columns}


def testActiveRowShowsTheBettingNumbers(qtbot) -> None:
    table = WagerTable(activeColumns)
    qtbot.addWidget(table)
    table.setWagers([
        Wager(
            title="Rain", side=Side.no, stake=25.0, price=0.4, fees=0.5,
            placedOn=date(2026, 10, 1), closesOn=date(2026, 10, 9), currentPrice=0.55,
        )
    ])

    texts = columnTexts(table, 0)

    assert texts["Side"] == "No"
    assert texts["Stake"] == "$25.00"
    assert texts["Odds"] == "40.0%"
    assert texts["Contracts"] == "62.50"
    assert texts["Max Win"] == "$62.50"
    assert texts["Profit If Won"] == "+$37.00"
    assert texts["Return"] == "+148%"
    assert texts["Now"] == "55.0%"
    assert texts["Value"] == "$34.38"
    assert texts["Placed"] == "2026-10-01"
    assert texts["Closes"] == "2026-10-09"


def testClosedRowShowsTheOutcome(qtbot) -> None:
    table = WagerTable(closedColumns)
    qtbot.addWidget(table)
    table.setWagers([
        Wager(
            title="Done", stake=20.0, price=0.25, fees=0.4, status=Status.won, payout=80.0,
            settledOn=date(2026, 10, 5),
        )
    ])

    texts = columnTexts(table, 0)

    assert texts["Result"] == "Won"
    assert texts["Payout"] == "$80.00"
    assert texts["P&L"] == "+$59.60"
    assert texts["Return"] == "+298%"
    assert texts["Settled"] == "2026-10-05"


def testUnknownValuesAreBlankNotZero(qtbot) -> None:
    table = WagerTable(activeColumns)
    qtbot.addWidget(table)
    table.setWagers([Wager(title="Sparse", stake=10.0, price=0.5)])

    texts = columnTexts(table, 0)

    assert texts["Now"] == "" and texts["Value"] == "" and texts["Closes"] == ""


def testGainsAndLossesAreColoured(qtbot) -> None:
    table = WagerTable(closedColumns)
    qtbot.addWidget(table)
    table.setWagers([
        Wager(title="Up", stake=10.0, price=0.5, status=Status.won, payout=20.0),
        Wager(title="Down", stake=10.0, price=0.5, status=Status.lost, payout=0.0),
    ])
    profitColumn = [c.title for c in closedColumns].index("P&L")
    model = table.tableModel

    up = model.data(model.index(0, profitColumn), Qt.ItemDataRole.ForegroundRole)
    down = model.data(model.index(1, profitColumn), Qt.ItemDataRole.ForegroundRole)

    assert up == gainColour and down == lossColour


def testSortingByStakeUsesDollarsNotText(qtbot) -> None:
    table = WagerTable(activeColumns)
    qtbot.addWidget(table)
    table.setWagers([
        Wager(title="Nine", stake=9.0, price=0.5),
        Wager(title="Thousand", stake=1000.0, price=0.5),
        Wager(title="Ninety", stake=90.0, price=0.5),
    ])
    stakeColumn = [c.title for c in activeColumns].index("Stake")

    table.sortByColumn(stakeColumn, Qt.SortOrder.DescendingOrder)

    titles = [columnTexts(table, row)["Title"] for row in range(3)]
    assert titles == ["Thousand", "Ninety", "Nine"]
    raw = table.proxy.data(table.proxy.index(0, stakeColumn), sortRole)
    assert raw == 1000.0


def testSelectionSurvivesARefresh(qtbot) -> None:
    table = WagerTable(activeColumns)
    qtbot.addWidget(table)
    first = Wager(title="First", stake=1.0, price=0.5)
    second = Wager(title="Second", stake=2.0, price=0.5)
    table.setWagers([first, second])
    assert table.selectWager(second.id)
    assert table.selectedWager() == second

    table.setWagers([second, first])

    assert table.selectedWager() == second


def testTheTitleColumnIsNeverSqueezedToNothing(qtbot) -> None:
    table = WagerTable(activeColumns)
    qtbot.addWidget(table)
    table.resize(600, 300)
    table.setWagers([Wager(title="Short", stake=1.0, price=0.5)])
    titleIndex = [c.title for c in activeColumns].index("Title")

    assert table.columnWidth(titleIndex) >= 320


def testSelectingAnUnknownIdSelectsNothing(qtbot) -> None:
    table = WagerTable(activeColumns)
    qtbot.addWidget(table)
    table.setWagers([Wager(title="Only", stake=1.0, price=0.5)])

    assert not table.selectWager("nobody")
    assert table.selectedWager() is None


def testDoubleClickActivatesTheWager(qtbot) -> None:
    table = WagerTable(activeColumns)
    qtbot.addWidget(table)
    wager = Wager(title="Open me", stake=1.0, price=0.5)
    table.setWagers([wager])
    activated: list[Wager] = []
    table.wagerActivated.connect(activated.append)

    table.onDoubleClicked(table.proxy.index(0, 0))

    assert activated == [wager]
