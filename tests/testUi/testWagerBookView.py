"""Tests for the Active / History book view over a real store in a temp folder."""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import Qt

from wagerBook.models.wager import Status, Wager
from wagerBook.services.priceService import PriceQuote, PriceRequest, PriceUpdate, SkippedPrice
from wagerBook.services.priceWorker import PriceWorker
from wagerBook.services.wagerStore import WagerStore
from wagerBook.services.wagerSummary import summarizeActive
from wagerBook.ui.wagers.wagerBookView import WagerBookView, activeSummaryText
from wagerBook.ui.wagers.wagerColumns import priceTip


def makeView(qtbot, tmp_path, wagers: list[Wager] | None = None) -> WagerBookView:
    store = WagerStore(tmp_path / "wagers.json")
    for wager in wagers or []:
        store.add(wager)
    view = WagerBookView(store)
    qtbot.addWidget(view)
    view.loadBook()
    return view


def answerDialog(monkeypatch, name: str, answer) -> None:
    monkeypatch.setattr(f"wagerBook.ui.wagers.wagerBookView.{name}", lambda *args: answer)


def rowTitles(table) -> list[str]:
    return [table.tableModel.wagerAt(row).title for row in range(table.tableModel.rowCount())]


def testAnEmptyBookExplainsItself(qtbot, tmp_path) -> None:
    view = makeView(qtbot, tmp_path)

    assert "No open wagers" in view.activeSummary.text()
    assert "No closed wagers" in view.historySummary.text()
    assert not view.editButton.isEnabled()
    assert not view.settleButton.isEnabled()
    assert not view.deleteButton.isEnabled()


def testOpenAndClosedWagersLandOnTheirOwnTabs(qtbot, tmp_path) -> None:
    view = makeView(qtbot, tmp_path, [
        Wager(title="Open", stake=10.0, price=0.5),
        Wager(title="Done", stake=10.0, price=0.5, status=Status.won, payout=20.0),
    ])

    assert rowTitles(view.activeTable) == ["Open"]
    assert rowTitles(view.historyTable) == ["Done"]
    assert "1 open" in view.activeSummary.text()
    assert "Max win $20.00" in view.activeSummary.text()
    assert "1 closed" in view.historySummary.text()
    assert "1 won, 0 lost" in view.historySummary.text()
    assert "Win rate 100%" in view.historySummary.text()
    assert "Net +$10.00" in view.historySummary.text()


def testAddingAWagerSavesAndSelectsIt(qtbot, tmp_path, monkeypatch) -> None:
    view = makeView(qtbot, tmp_path)
    new = Wager(title="Fresh", stake=5.0, price=0.5)
    answerDialog(monkeypatch, "editWager", new)
    messages: list[str] = []
    view.statusMessage.connect(messages.append)

    view.onAdd()

    assert rowTitles(view.activeTable) == ["Fresh"]
    assert view.activeTable.selectedWager() == new
    assert view.editButton.isEnabled()
    assert messages == ["Added: Fresh"]
    reopened = WagerStore(view.store.path)
    reopened.load()
    assert [w.title for w in reopened.wagers] == ["Fresh"]


def testCancellingTheAddDialogChangesNothing(qtbot, tmp_path, monkeypatch) -> None:
    view = makeView(qtbot, tmp_path)
    answerDialog(monkeypatch, "editWager", None)

    view.onAdd()

    assert view.store.wagers == []
    assert not view.store.path.exists()


def testEditingReplacesTheSelectedWager(qtbot, tmp_path, monkeypatch) -> None:
    original = Wager(title="Before", stake=5.0, price=0.5)
    view = makeView(qtbot, tmp_path, [original])
    view.activeTable.selectWager(original.id)
    changed = Wager.fromDict(original.toDict())
    changed.title = "After"
    answerDialog(monkeypatch, "editWager", changed)

    view.onEdit()

    assert rowTitles(view.activeTable) == ["After"]
    assert len(view.store.wagers) == 1


def testSettlingMovesTheWagerToHistory(qtbot, tmp_path, monkeypatch) -> None:
    wager = Wager(title="Rain", stake=10.0, price=0.5)
    view = makeView(qtbot, tmp_path, [wager])
    view.activeTable.selectWager(wager.id)
    answerDialog(monkeypatch, "settleWager", (Status.won, 20.0, date(2026, 10, 2)))
    messages: list[str] = []
    view.statusMessage.connect(messages.append)

    view.onSettle()

    assert rowTitles(view.activeTable) == []
    assert rowTitles(view.historyTable) == ["Rain"]
    selected = view.historyTable.selectedWager()
    assert selected is not None and selected.id == wager.id
    assert selected.status == Status.won
    assert messages == ["Won: Rain, net +$10.00"]
    assert "No open wagers" in view.activeSummary.text()


def testReopenBringsItBack(qtbot, tmp_path) -> None:
    wager = Wager(title="Oops", stake=10.0, price=0.5, status=Status.lost, payout=0.0)
    view = makeView(qtbot, tmp_path, [wager])
    view.historyTable.selectWager(wager.id)

    view.onReopen()

    assert rowTitles(view.activeTable) == ["Oops"]
    assert rowTitles(view.historyTable) == []
    selected = view.activeTable.selectedWager()
    assert selected is not None and selected.id == wager.id
    assert selected.isActive and selected.payout is None


def testTheRowButtonsStillWorkOnTheSelectedRow(qtbot, tmp_path, monkeypatch) -> None:
    """With highlights cleared on any click away, a press on Edit or Settle must not
    count as one - or the button would disable itself before its click landed."""
    wager = Wager(title="Rain", stake=10.0, price=0.5)
    view = makeView(qtbot, tmp_path, [wager])
    view.resize(1000, 500)
    view.show()
    qtbot.waitExposed(view)
    view.activeTable.selectWager(wager.id)
    edited: list[str] = []
    monkeypatch.setattr(
        "wagerBook.ui.wagers.wagerBookView.editWager",
        lambda parent, chosen: edited.append(chosen.title) or None,
    )

    qtbot.mouseClick(view.editButton, Qt.MouseButton.LeftButton)

    assert edited == ["Rain"]
    assert view.activeTable.selectedWager() is not None


def testClickingAddClearsTheOldHighlight(qtbot, tmp_path, monkeypatch) -> None:
    wager = Wager(title="Rain", stake=10.0, price=0.5)
    view = makeView(qtbot, tmp_path, [wager])
    view.show()
    qtbot.waitExposed(view)
    view.activeTable.selectWager(wager.id)
    answerDialog(monkeypatch, "editWager", None)  # Add is cancelled

    qtbot.mouseClick(view.addButton, Qt.MouseButton.LeftButton)

    assert view.activeTable.selectedWager() is None
    assert not view.editButton.isEnabled()


def testDeleteAsksFirstAndHonoursNo(qtbot, tmp_path, monkeypatch) -> None:
    wager = Wager(title="Keep", stake=10.0, price=0.5)
    view = makeView(qtbot, tmp_path, [wager])
    view.activeTable.selectWager(wager.id)
    asked: list[str] = []
    monkeypatch.setattr(
        WagerBookView, "confirm", lambda self, title, question: asked.append(question) or False
    )

    view.onDelete()

    assert asked and "Keep" in asked[0]
    assert rowTitles(view.activeTable) == ["Keep"]


def testDeleteRemovesOnYes(qtbot, tmp_path, monkeypatch) -> None:
    wager = Wager(title="Gone", stake=10.0, price=0.5)
    view = makeView(qtbot, tmp_path, [wager])
    view.activeTable.selectWager(wager.id)
    monkeypatch.setattr(WagerBookView, "confirm", lambda self, title, question: True)

    view.onDelete()

    assert view.store.wagers == []


def testDeleteOnTheHistoryTabUsesThatTable(qtbot, tmp_path, monkeypatch) -> None:
    done = Wager(title="Done", stake=10.0, price=0.5, status=Status.won, payout=20.0)
    view = makeView(qtbot, tmp_path, [Wager(title="Open", stake=1.0, price=0.5), done])
    view.showHistory()
    view.historyTable.selectWager(done.id)
    monkeypatch.setattr(WagerBookView, "confirm", lambda self, title, question: True)

    view.onDelete()

    assert [w.title for w in view.store.wagers] == ["Open"]


def testASaveFailureIsReportedAndTheRowsStayHonest(qtbot, tmp_path, monkeypatch) -> None:
    view = makeView(qtbot, tmp_path)
    errors: list[tuple[str, str]] = []
    view.errorMessage.connect(lambda title, message: errors.append((title, message)))
    # Make the book's folder a file, so the next save cannot write.
    view.store.path = tmp_path / "blocker" / "wagers.json"
    (tmp_path / "blocker").write_text("not a folder", encoding="utf-8")
    answerDialog(monkeypatch, "editWager", Wager(title="Unsaved", stake=1.0, price=0.5))

    view.onAdd()

    assert errors and errors[0][0] == "Wager Book"
    assert "Could not save" in errors[0][1]
    assert rowTitles(view.activeTable) == ["Unsaved"]


# ------------------------------------------------------- update prices ----


class CannedPrices:
    """Stands in for PriceService: answers at once, no network."""

    def __init__(self, makeUpdate) -> None:
        self.makeUpdate = makeUpdate
        self.asked: list[PriceRequest] = []

    def updateAll(self, requests):
        self.asked = list(requests)
        return self.makeUpdate(requests)


def runPriceUpdate(qtbot, view: WagerBookView, monkeypatch, makeUpdate) -> CannedPrices:
    canned = CannedPrices(makeUpdate)
    monkeypatch.setattr(
        WagerBookView, "makePriceWorker",
        lambda self, requests: PriceWorker(requests, priceService=canned, parent=self),
    )
    with qtbot.waitSignal(view.priceUpdateRunning, timeout=5000,
                          check_params_cb=lambda running: running is False):
        view.startPriceUpdate()
        assert not view.updatePricesButton.isEnabled()  # one run at a time
    return canned


pricedMoment = datetime(2026, 10, 16, 9, 42)


def testUpdatePricesSetsNowAndValueAndSaysHowMany(qtbot, tmp_path, monkeypatch) -> None:
    linked = Wager(title="Ken Paxton", stake=9.99, price=0.396271, ticker="SENATETX-26")
    unlinked = Wager(title="No ticker yet", stake=5.0, price=0.5)
    done = Wager(title="Done", stake=1.0, price=0.5, status=Status.won, payout=2.0)
    view = makeView(qtbot, tmp_path, [linked, unlinked, done])
    messages: list[str] = []
    errors: list[tuple[str, str]] = []
    view.statusMessage.connect(messages.append)
    view.errorMessage.connect(lambda title, message: errors.append((title, message)))

    def answer(requests):
        byId = {request.wagerId: request for request in requests}
        return PriceUpdate(
            at=pricedMoment,
            quotes=[PriceQuote(linked.id, 0.38, "SENATETX-26-R")],
            skipped=[SkippedPrice(byId[unlinked.id], "no ticker: paste the address")],
        )

    canned = runPriceUpdate(qtbot, view, monkeypatch, answer)

    assert {request.wagerId for request in canned.asked} == {linked.id, unlinked.id}
    priced = view.store.find(linked.id)
    assert priced.currentPrice == 0.38
    assert priced.ticker == "SENATETX-26-R"
    assert priced.pricedAt == pricedMoment
    assert view.updatePricesButton.isEnabled()
    assert messages[-1].startswith("Prices updated for 1 of 2 open wagers at 09:42.")
    assert "1 have no ticker yet" in messages[-1]
    assert errors == []  # a missing ticker is a hint, not a failure
    assert "Worth now $9.58 (1 priced), -$0.41" in view.activeSummary.text()


def testWagersThatCouldNotBePricedAreListedWithTheReason(qtbot, tmp_path, monkeypatch) -> None:
    wager = Wager(title="Texas Senate winner?", stake=10.0, price=0.4, ticker="SENATETX-26")
    view = makeView(qtbot, tmp_path, [wager])
    errors: list[tuple[str, str]] = []
    view.errorMessage.connect(lambda title, message: errors.append((title, message)))

    def answer(requests):
        reason = "several markets and none of their names is in the title: Ken Paxton"
        return PriceUpdate(at=pricedMoment, skipped=[SkippedPrice(requests[0], reason)])

    runPriceUpdate(qtbot, view, monkeypatch, answer)

    assert errors and errors[0][0] == "Update Prices"
    assert "Texas Senate winner?: several markets" in errors[0][1]
    assert view.store.find(wager.id).currentPrice is None


def testNoConnectionChangesNothingAndSaysSo(qtbot, tmp_path, monkeypatch) -> None:
    wager = Wager(title="Paxton", stake=10.0, price=0.4, ticker="SENATETX-26-R",
                  currentPrice=0.41, pricedAt=datetime(2026, 10, 15, 8, 0))
    view = makeView(qtbot, tmp_path, [wager])
    errors: list[tuple[str, str]] = []
    view.errorMessage.connect(lambda title, message: errors.append((title, message)))

    def answer(requests):
        return PriceUpdate(at=pricedMoment, skipped=[SkippedPrice(
            requests[0], "could not reach api.elections.kalshi.com: timed out", unreachable=True)])

    runPriceUpdate(qtbot, view, monkeypatch, answer)

    assert errors and "Neither price site answered" in errors[0][1]
    assert "timed out" in errors[0][1]
    kept = view.store.find(wager.id)
    assert kept.currentPrice == 0.41 and kept.pricedAt == datetime(2026, 10, 15, 8, 0)


def testNoOpenWagersNeedsNoUpdate(qtbot, tmp_path) -> None:
    view = makeView(qtbot, tmp_path)
    messages: list[str] = []
    view.statusMessage.connect(messages.append)

    view.startPriceUpdate()

    assert messages == ["No open wagers to price."]
    assert view.priceWorker is None


def testTheTotalsSayHowOldThePricesAre() -> None:
    wagers = [
        Wager(title="A", stake=10.0, price=0.5, currentPrice=0.6,
              pricedAt=datetime(2026, 10, 15, 8, 5)),
        Wager(title="B", stake=10.0, price=0.5, currentPrice=0.4,
              pricedAt=datetime(2026, 10, 16, 9, 42)),
    ]

    text = activeSummaryText(summarizeActive(wagers), now=datetime(2026, 10, 16, 12, 0))

    # 12 + 8 = 20 worth now against 20 staked; the oldest price sets the age.
    assert "Worth now $20.00, $0.00, prices from Oct 15 08:05" in text
    assert "priced)" not in text  # every open wager has a price


def testTypedPricesAreNotPassedOffAsFetched() -> None:
    """One fresh fetch must not make fourteen typed-in prices look current."""
    now = datetime(2026, 10, 16, 12, 0)
    fetched = Wager(title="A", stake=10.0, price=0.5, currentPrice=0.6,
                    pricedAt=datetime(2026, 10, 16, 9, 42))
    typed = Wager(title="B", stake=10.0, price=0.5, currentPrice=0.4)

    mixed = activeSummaryText(summarizeActive([fetched, typed]), now=now)
    byHand = activeSummaryText(summarizeActive([typed]), now=now)

    assert "1 of 2 prices fetched (oldest 09:42), the rest typed in" in mixed
    assert byHand.endswith(", prices entered by hand")


def testThePriceCellsSayWhereThePriceCameFrom() -> None:
    fetched = Wager(title="A", currentPrice=0.4, pricedAt=datetime(2026, 10, 16, 9, 42))
    typed = Wager(title="B", currentPrice=0.4)
    none = Wager(title="C")

    assert priceTip(fetched) == "Sell price as of 2026-10-16 09:42"
    assert priceTip(typed) == "Entered by hand"
    assert "Update Prices" in priceTip(none)
