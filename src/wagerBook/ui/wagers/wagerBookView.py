"""The book itself: an Active tab and a History tab over one store.

Every change goes through the store and then both tabs are redrawn from it,
so there is one truth and nothing to keep in step by hand.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wagerBook.models.wager import Wager
from wagerBook.services.priceService import PriceRequest, PriceUpdate
from wagerBook.services.priceWorker import PriceWorker
from wagerBook.services.wagerStore import WagerStore, WagerStoreError
from wagerBook.services.wagerSummary import (
    ActiveSummary,
    ClosedSummary,
    summarizeActive,
    summarizeClosed,
)
from wagerBook.ui.dialogs.settleDialog import settleWager
from wagerBook.ui.dialogs.wagerDialog import editWager
from wagerBook.ui.wagers.wagerColumns import activeColumns, closedColumns, money, signedMoney
from wagerBook.ui.wagers.wagerTable import WagerTable
from wagerBook.ui.widgets.fullWidthTabWidget import FullWidthTabWidget
from wagerBook.ui.widgets.reportingView import ReportingView


def momentText(moment: datetime, now: datetime | None = None) -> str:
    """"09:42" today, "Oct 15 09:42" before."""
    today = (now or datetime.now()).date()
    return f"{moment:%H:%M}" if moment.date() == today else f"{moment:%b %d %H:%M}"


def activeSummaryText(summary: ActiveSummary, now: datetime | None = None) -> str:
    if summary.count == 0:
        return "No open wagers. Add one with the button above or Ctrl+N."
    text = (
        f"{summary.count} open  ·  Staked {money(summary.staked)}  ·  "
        f"Max win {money(summary.maxPayout)}  ·  "
        f"Profit if all won {signedMoney(summary.maxProfit)}"
    )
    if summary.priced:
        which = "" if summary.priced == summary.count else f" ({summary.priced} priced)"
        text += (
            f"  ·  Worth now {money(summary.value)}{which}, "
            f"{signedMoney(summary.unrealized)}"
        )
        text += priceAgeText(summary, now)
    return text


def priceAgeText(summary: ActiveSummary, now: datetime | None = None) -> str:
    """How fresh "worth now" is - never fresher than the prices behind it."""
    if summary.fetched == 0 or summary.oldestPrice is None:
        return ", prices entered by hand"
    oldest = momentText(summary.oldestPrice, now)
    if summary.fetched == summary.priced:
        return f", prices from {oldest}"
    return (
        f", {summary.fetched} of {summary.priced} prices fetched (oldest {oldest}),"
        " the rest typed in"
    )


def priceStatusText(changed: int, update: PriceUpdate) -> str:
    total = len(update.quotes) + len(update.skipped)
    text = f"Prices updated for {changed} of {total} open wagers at {update.at:%H:%M}."
    missing = sum(1 for skip in update.skipped if not skip.request.ticker)
    if missing:
        text += (
            f" {missing} have no ticker yet: open each one and paste the market's"
            " address into Ticker."
        )
    return text


def priceProblemsText(update: PriceUpdate) -> str | None:
    """The wagers that were looked up and still could not be priced, and why."""
    problems = [skip for skip in update.skipped if skip.request.ticker]
    if not problems:
        return None
    lines = "\n".join(f"• {skip.request.title}: {skip.reason}" for skip in problems)
    return (
        f"{len(problems)} open wager{'' if len(problems) == 1 else 's'} could not be priced."
        f"\n\n{lines}\n\nTheir old prices are kept."
    )


def closedSummaryText(summary: ClosedSummary) -> str:
    if summary.count == 0:
        return "No closed wagers yet. Settle an open one and it moves here."
    outcomes = [f"{summary.won} won", f"{summary.lost} lost"]
    if summary.sold:
        outcomes.append(f"{summary.sold} sold")
    if summary.voided:
        outcomes.append(f"{summary.voided} voided")
    rate = "" if summary.winRate is None else f"  ·  Win rate {summary.winRate * 100:.0f}%"
    return (
        f"{summary.count} closed  ·  {', '.join(outcomes)}{rate}  ·  "
        f"Staked {money(summary.staked)}  ·  Returned {money(summary.returned)}  ·  "
        f"Net {signedMoney(summary.profit)}"
    )


class WagerBookView(ReportingView):
    # True while Update Prices is running, so the window can grey its menu item.
    priceUpdateRunning = Signal(bool)

    def __init__(self, store: WagerStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.priceWorker: PriceWorker | None = None

        self.tabs = FullWidthTabWidget()
        self.activeTable = WagerTable(activeColumns)
        self.historyTable = WagerTable(closedColumns)

        self.addButton = QPushButton("Add...")
        self.editButton = QPushButton("Edit...")
        self.settleButton = QPushButton("Settle...")
        self.deleteButton = QPushButton("Delete")
        self.updatePricesButton = QPushButton("Update Prices")
        self.updatePricesButton.setToolTip(
            "Fetch what each open wager could be sold for now, from Kalshi and Polymarket (F5)"
        )
        self.activeSummary = QLabel()
        self.activeSummary.setWordWrap(True)
        self.activePage = self.buildPage(
            self.activeTable,
            [self.addButton, self.editButton, self.settleButton, self.deleteButton],
            self.activeSummary,
            trailing=[self.updatePricesButton],
        )
        self.tabs.addTab(self.activePage, "Active")

        self.historyEditButton = QPushButton("Edit...")
        self.reopenButton = QPushButton("Reopen")
        self.historyDeleteButton = QPushButton("Delete")
        self.historySummary = QLabel()
        self.historyPage = self.buildPage(
            self.historyTable,
            [self.historyEditButton, self.reopenButton, self.historyDeleteButton],
            self.historySummary,
        )
        self.tabs.addTab(self.historyPage, "History")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

        self.addButton.clicked.connect(self.onAdd)
        self.editButton.clicked.connect(self.onEdit)
        self.settleButton.clicked.connect(self.onSettle)
        self.deleteButton.clicked.connect(self.onDelete)
        self.historyEditButton.clicked.connect(self.onEdit)
        self.reopenButton.clicked.connect(self.onReopen)
        self.historyDeleteButton.clicked.connect(self.onDelete)
        self.updatePricesButton.clicked.connect(self.startPriceUpdate)
        # These act on the selected row: pressing one must not clear it first.
        self.activeTable.keepSelectionFor(
            [self.editButton, self.settleButton, self.deleteButton]
        )
        self.historyTable.keepSelectionFor(
            [self.historyEditButton, self.reopenButton, self.historyDeleteButton]
        )
        for table in (self.activeTable, self.historyTable):
            table.wagerActivated.connect(self.editWager)
            table.selectedWagerChanged.connect(self.refreshButtons)
        self.tabs.currentChanged.connect(self.refreshButtons)
        self.refresh()

    @staticmethod
    def buildPage(
        table: WagerTable,
        buttons: list[QPushButton],
        summary: QLabel,
        trailing: list[QPushButton] | None = None,
    ) -> QWidget:
        """Row buttons on the left; whole-table ones, like Update Prices, on the right."""
        page = QWidget()
        layout = QVBoxLayout(page)
        buttonRow = QHBoxLayout()
        for button in buttons:
            buttonRow.addWidget(button)
        buttonRow.addStretch()
        for button in trailing or []:
            buttonRow.addWidget(button)
        layout.addLayout(buttonRow)
        layout.addWidget(table, 1)
        layout.addWidget(summary)
        return page

    # ----------------------------------------------------------- state ----

    def loadBook(self) -> None:
        try:
            self.store.load()
        except WagerStoreError as exc:
            self.reportError("Wager Book", str(exc))
        self.refresh()

    def refresh(self) -> None:
        self.activeTable.setWagers(self.store.active())
        self.historyTable.setWagers(self.store.closed())
        self.activeSummary.setText(activeSummaryText(summarizeActive(self.store.wagers)))
        self.historySummary.setText(closedSummaryText(summarizeClosed(self.store.wagers)))
        self.refreshButtons()

    def refreshButtons(self, *_args) -> None:
        hasActive = self.activeTable.selectedWager() is not None
        for button in (self.editButton, self.settleButton, self.deleteButton):
            button.setEnabled(hasActive)
        hasClosed = self.historyTable.selectedWager() is not None
        for button in (self.historyEditButton, self.reopenButton, self.historyDeleteButton):
            button.setEnabled(hasClosed)

    def currentTable(self) -> WagerTable:
        if self.tabs.currentWidget() is self.historyPage:
            return self.historyTable
        return self.activeTable

    def showActive(self) -> None:
        self.tabs.setCurrentWidget(self.activePage)

    def showHistory(self) -> None:
        self.tabs.setCurrentWidget(self.historyPage)

    def selectedWager(self) -> Wager | None:
        return self.currentTable().selectedWager()

    def confirm(self, title: str, question: str) -> bool:
        """A method so tests can answer without a box opening."""
        answer = QMessageBox.question(
            self, title, question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def applyChange(self, change: Callable[[], str]) -> None:
        """Run a store change; its status goes to the bar, a failure to a dialog.

        The table is redrawn either way: a failed save still changed what is
        in memory, and showing that honestly beats showing the old rows.
        """
        try:
            message = change()
        except WagerStoreError as exc:
            self.reportError("Wager Book", str(exc))
        else:
            self.reportStatus(message)
        self.refresh()

    # --------------------------------------------------------- actions ----

    def onAdd(self) -> None:
        wager = editWager(self, None)
        if wager is None:
            return

        def add() -> str:
            self.store.add(wager)
            return f"Added: {wager.title}"

        self.applyChange(add)
        self.showActive()
        self.activeTable.selectWager(wager.id)

    def onEdit(self) -> None:
        wager = self.selectedWager()
        if wager is not None:
            self.editWager(wager)

    def editWager(self, wager: Wager) -> None:
        changed = editWager(self, wager)
        if changed is None:
            return

        def update() -> str:
            self.store.update(changed)
            return f"Updated: {changed.title}"

        self.applyChange(update)

    def onSettle(self) -> None:
        wager = self.activeTable.selectedWager()
        if wager is None:
            return
        settlement = settleWager(self, wager)
        if settlement is None:
            return
        status, payout, settledOn = settlement

        def settle() -> str:
            settled = self.store.settle(wager.id, status, payout, settledOn)
            return f"{status}: {settled.title}, net {signedMoney(settled.realizedProfit)}"

        self.applyChange(settle)
        self.historyTable.selectWager(wager.id)

    def onReopen(self) -> None:
        wager = self.historyTable.selectedWager()
        if wager is None:
            return

        def reopen() -> str:
            self.store.reopen(wager.id)
            return f"Reopened: {wager.title}"

        self.applyChange(reopen)
        self.activeTable.selectWager(wager.id)

    def onDelete(self) -> None:
        wager = self.selectedWager()
        if wager is None:
            return
        if not self.confirm(
            "Delete Wager",
            f"Delete \"{wager.title}\"?\n\nThis removes it from the book for good; "
            "a wager that lost should be settled, not deleted.",
        ):
            return

        def remove() -> str:
            self.store.remove(wager.id)
            return f"Deleted: {wager.title}"

        self.applyChange(remove)

    # ---------------------------------------------------- update prices ----

    def makePriceWorker(self, requests: list[PriceRequest]) -> PriceWorker:
        """A method so tests can hand in a worker that never touches the network."""
        return PriceWorker(requests, parent=self)

    def startPriceUpdate(self) -> None:
        """Fetch today's sell price for every open wager, off the interface thread."""
        if self.priceWorker is not None:
            return
        requests = [PriceRequest.fromWager(wager) for wager in self.store.active()]
        if not requests:
            self.reportStatus("No open wagers to price.")
            return
        self.updatePricesButton.setEnabled(False)
        self.priceUpdateRunning.emit(True)
        self.reportStatus(f"Updating prices for {len(requests)} open wagers...")
        worker = self.makePriceWorker(requests)
        worker.finishedUpdate.connect(self.onPricesUpdated)
        worker.finished.connect(self.onPriceWorkerFinished)
        self.priceWorker = worker
        worker.start()

    def onPricesUpdated(self, update: PriceUpdate) -> None:
        if update.nothingReached:
            unreachable = {skip.reason for skip in update.skipped if skip.unreachable}
            reasons = "\n".join(sorted(unreachable))
            self.reportError(
                "Update Prices",
                "Neither price site answered, so no prices were changed.\n\n"
                f"{reasons}\n\nCheck the internet connection and try again.",
            )
            return

        def apply() -> str:
            quotes = [(quote.wagerId, quote.price, quote.ticker) for quote in update.quotes]
            changed = self.store.applyPrices(quotes, update.at) if quotes else 0
            return priceStatusText(changed, update)

        self.applyChange(apply)
        problems = priceProblemsText(update)
        if problems:
            self.errorMessage.emit("Update Prices", problems)

    def onPriceWorkerFinished(self) -> None:
        if self.priceWorker is not None:
            self.priceWorker.deleteLater()
            self.priceWorker = None
        self.updatePricesButton.setEnabled(True)
        self.priceUpdateRunning.emit(False)

    def waitForPriceUpdate(self, milliseconds: int) -> None:
        """For closing: a thread left running into interpreter shutdown crashes the exit."""
        if self.priceWorker is not None:
            self.priceWorker.wait(milliseconds)
