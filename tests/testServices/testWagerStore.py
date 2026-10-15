"""Tests for the JSON wager book."""

from __future__ import annotations

import json
from datetime import date

import pytest

from wagerBook.models.wager import Status, Wager
from wagerBook.services.wagerStore import WagerStore, WagerStoreError


def openStore(tmp_path) -> WagerStore:
    store = WagerStore(tmp_path / "book" / "wagers.json")
    store.load()
    return store


def testAMissingFileIsAnEmptyBook(tmp_path) -> None:
    store = openStore(tmp_path)

    assert store.wagers == []
    assert not store.path.exists()


def testAddingWritesTheFileAndItLoadsBack(tmp_path) -> None:
    store = openStore(tmp_path)
    wager = Wager(title="Rain", stake=10.0, price=0.5, placedOn=date(2026, 10, 1))

    store.add(wager)

    assert store.path.exists()
    reopened = openStore(tmp_path)
    assert reopened.wagers == [wager]
    assert json.loads(store.path.read_text(encoding="utf-8"))["version"] == 1


def testNoTemporaryFileIsLeftBehind(tmp_path) -> None:
    store = openStore(tmp_path)

    store.add(Wager(title="Rain"))

    assert [path.name for path in store.path.parent.iterdir()] == ["wagers.json"]


def testUpdateReplacesByIdInPlace(tmp_path) -> None:
    store = openStore(tmp_path)
    first = Wager(title="First")
    second = Wager(title="Second")
    store.add(first)
    store.add(second)

    changed = Wager.fromDict(first.toDict())
    changed.title = "First, corrected"
    store.update(changed)

    assert [wager.title for wager in store.wagers] == ["First, corrected", "Second"]
    assert openStore(tmp_path).wagers[0].title == "First, corrected"


def testUpdatingAnUnknownWagerIsAnError(tmp_path) -> None:
    store = openStore(tmp_path)

    with pytest.raises(KeyError):
        store.update(Wager(title="Nobody"))


def testRemove(tmp_path) -> None:
    store = openStore(tmp_path)
    wager = Wager(title="Gone")
    store.add(wager)

    store.remove(wager.id)

    assert store.wagers == []
    assert openStore(tmp_path).wagers == []


def testSettleMovesAWagerFromActiveToClosed(tmp_path) -> None:
    store = openStore(tmp_path)
    wager = Wager(title="Rain", stake=10.0, price=0.5)
    store.add(wager)
    assert store.active() == [wager] and store.closed() == []

    settled = store.settle(wager.id, Status.won, 20.0, date(2026, 10, 2))

    assert settled.status == Status.won
    assert settled.payout == 20.0
    assert settled.settledOn == date(2026, 10, 2)
    assert store.active() == [] and store.closed() == [wager]
    assert openStore(tmp_path).closed()[0].realizedProfit == pytest.approx(10.0)


def testSettlingAsActiveIsRefused(tmp_path) -> None:
    store = openStore(tmp_path)
    wager = Wager(title="Rain")
    store.add(wager)

    with pytest.raises(ValueError):
        store.settle(wager.id, Status.active, 0.0, date.today())


def testReopenClearsTheSettlement(tmp_path) -> None:
    store = openStore(tmp_path)
    wager = Wager(title="Rain", stake=10.0, price=0.5)
    store.add(wager)
    store.settle(wager.id, Status.lost, 0.0, date(2026, 10, 2))

    reopened = store.reopen(wager.id)

    assert reopened.isActive
    assert reopened.payout is None and reopened.settledOn is None
    assert openStore(tmp_path).active() == [wager]


def testACorruptFileSaysWhereItIs(tmp_path) -> None:
    path = tmp_path / "wagers.json"
    path.write_text("{not json", encoding="utf-8")
    store = WagerStore(path)

    with pytest.raises(WagerStoreError) as caught:
        store.load()

    assert str(path) in str(caught.value)


def testABareListStillLoads(tmp_path) -> None:
    """The file is hand-editable; a list without the version wrapper is fine."""
    path = tmp_path / "wagers.json"
    path.write_text(json.dumps([Wager(title="Bare").toDict()]), encoding="utf-8")
    store = WagerStore(path)

    store.load()

    assert [wager.title for wager in store.wagers] == ["Bare"]


def testAnUnwritablePathSaysSo(tmp_path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a folder", encoding="utf-8")
    store = WagerStore(blocker / "wagers.json")

    with pytest.raises(WagerStoreError) as caught:
        store.add(Wager(title="Rain"))

    assert "Could not save" in str(caught.value)
    assert str(store.path) in str(caught.value)
