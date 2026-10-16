"""Tests for the table model, its formatting, and sorting by real values."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton, QVBoxLayout, QWidget

from wagerBook.models.wager import Side, Status, Wager
from wagerBook.ui.wagers.wagerColumns import (
    activeColumns,
    closedColumns,
    money,
    oddsPercent,
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
    assert oddsPercent(0.11684919) == "11.685%"
    assert oddsPercent(None) == ""
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
    assert texts["Odds"] == "40.000%"
    assert texts["Now"] == "55.0%"  # the market's price stays at a tenth
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


def testNoColumnRepeatsMaxWin() -> None:
    """A contract pays $1, so a Contracts column would be Max Win again."""
    titles = [column.title for column in activeColumns]
    assert "Contracts" not in titles
    assert "Max Win" in titles


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


def testValueIsGreenAboveWhatTheWagerCostAndRedBelow(qtbot) -> None:
    table = WagerTable(activeColumns)
    qtbot.addWidget(table)
    table.setWagers([
        # 100 contracts each; worth 100 x the current price.
        Wager(title="Up", stake=40.0, price=0.4, currentPrice=0.45),        # $45 vs $40
        Wager(title="Down", stake=40.0, price=0.4, currentPrice=0.35),      # $35 vs $40
        Wager(title="Even", stake=40.0, price=0.4, currentPrice=0.4),       # $40 vs $40
        Wager(title="Fees", stake=40.0, price=0.4, fees=1.0, currentPrice=0.405),  # $40.50 vs $41
        Wager(title="Unpriced", stake=40.0, price=0.4),
    ])
    valueColumn = [c.title for c in activeColumns].index("Value")
    model = table.tableModel

    def colour(row: int):
        return model.data(model.index(row, valueColumn), Qt.ItemDataRole.ForegroundRole)

    assert colour(0) == gainColour
    assert colour(1) == lossColour
    assert colour(2) is None
    assert colour(3) == lossColour  # above the stake, still below stake plus fees
    assert colour(4) is None


def testTheValueTipSaysWhatTheColourMeans(qtbot) -> None:
    table = WagerTable(activeColumns)
    qtbot.addWidget(table)
    table.setWagers([Wager(title="Down", stake=40.0, price=0.4, fees=1.0, currentPrice=0.35)])
    valueColumn = [c.title for c in activeColumns].index("Value")

    tip = table.tableModel.data(table.tableModel.index(0, valueColumn), Qt.ItemDataRole.ToolTipRole)

    assert "Entered by hand" in tip
    assert "-$6.00 against the $41.00 it cost" in tip


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


def tableInAWindow(qtbot) -> tuple[QWidget, WagerTable, QPushButton, QPushButton, QLineEdit]:
    """A table with two rows, a button that uses the selection, one that does not,
    and a text box - the shape of the Active tab."""
    window = QWidget()
    layout = QVBoxLayout(window)
    table = WagerTable(activeColumns)
    keeper = QPushButton("Edit...")
    other = QPushButton("Add...")
    textBox = QLineEdit()
    for widget in (keeper, other, textBox, table):
        layout.addWidget(widget)
    table.keepSelectionFor([keeper])
    table.setWagers([
        Wager(title="First", stake=1.0, price=0.5),
        Wager(title="Second", stake=2.0, price=0.5),
    ])
    qtbot.addWidget(window)
    window.resize(900, 500)
    window.show()
    qtbot.waitExposed(window)
    return window, table, keeper, other, textBox


def rowCentre(table: WagerTable, row: int) -> QPoint:
    return table.visualRect(table.proxy.index(row, 2)).center()


def testClickingARowSelectsIt(qtbot) -> None:
    _window, table, _keeper, _other, _textBox = tableInAWindow(qtbot)

    qtbot.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=rowCentre(table, 1))

    assert table.selectedWager() is not None
    assert table.selectedWager().title == "Second"


def testClickingAnotherControlClearsTheHighlight(qtbot) -> None:
    _window, table, _keeper, other, textBox = tableInAWindow(qtbot)
    for target in (other, textBox):
        table.selectRow(0)
        assert table.selectedWager() is not None

        qtbot.mouseClick(target, Qt.MouseButton.LeftButton)

        assert table.selectedWager() is None
        assert not table.currentIndex().isValid()  # no focus box left on a cell either


def testAButtonThatUsesTheSelectionKeepsIt(qtbot) -> None:
    """Pressing Edit must not clear the row Edit is about to open."""
    _window, table, keeper, _other, _textBox = tableInAWindow(qtbot)
    seen: list[str | None] = []
    keeper.clicked.connect(
        lambda: seen.append(table.selectedWager().title if table.selectedWager() else None)
    )
    table.selectRow(1)

    qtbot.mouseClick(keeper, Qt.MouseButton.LeftButton)

    assert seen == ["Second"]
    assert table.selectedWager() is not None


def testTheBlankSpaceBelowTheRowsClearsTheHighlight(qtbot) -> None:
    _window, table, _keeper, _other, _textBox = tableInAWindow(qtbot)
    table.selectRow(0)
    blank = QPoint(20, table.viewport().height() - 10)
    assert not table.indexAt(blank).isValid()

    qtbot.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=blank)

    assert table.selectedWager() is None


def testSortingByAHeaderKeepsTheRow(qtbot) -> None:
    _window, table, _keeper, _other, _textBox = tableInAWindow(qtbot)
    table.selectRow(0)
    header = table.horizontalHeader()
    stakeColumn = [c.title for c in activeColumns].index("Stake")
    centre = QPoint(header.sectionViewportPosition(stakeColumn) + 10, header.height() // 2)

    qtbot.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, pos=centre)

    assert table.selectedWager() is not None
    assert table.selectedWager().title == "First"


def testAClickInAnotherWindowLeavesTheSelectionAlone(qtbot) -> None:
    """The edit form a row opens is not a click away from that row."""
    _window, table, _keeper, _other, _textBox = tableInAWindow(qtbot)
    dialog = QDialog()
    dialogButton = QPushButton("OK", dialog)
    qtbot.addWidget(dialog)
    dialog.show()
    table.selectRow(1)

    qtbot.mouseClick(dialogButton, Qt.MouseButton.LeftButton)

    assert table.selectedWager() is not None


def testDoubleClickActivatesTheWager(qtbot) -> None:
    table = WagerTable(activeColumns)
    qtbot.addWidget(table)
    wager = Wager(title="Open me", stake=1.0, price=0.5)
    table.setWagers([wager])
    activated: list[Wager] = []
    table.wagerActivated.connect(activated.append)

    table.onDoubleClicked(table.proxy.index(0, 0))

    assert activated == [wager]
