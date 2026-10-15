"""Tests for the Active / History book view over a real store in a temp folder."""

from __future__ import annotations

from datetime import date

from wagerBook.models.wager import Status, Wager
from wagerBook.services.wagerStore import WagerStore
from wagerBook.ui.wagers.wagerBookView import WagerBookView


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
