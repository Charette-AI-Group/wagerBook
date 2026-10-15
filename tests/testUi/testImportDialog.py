"""Tests for the import preview."""

from __future__ import annotations

from pathlib import Path

from wagerBook.models.wager import Platform, Wager
from wagerBook.services.importService import ImportResult, SkippedRow
from wagerBook.ui.dialogs.importDialog import ImportPreviewDialog


def sampleResult() -> ImportResult:
    return ImportResult(
        path=Path("C:/exports/fills.csv"),
        platform=Platform.kalshi,
        toAdd=[Wager(title="One", stake=5.0, price=0.5), Wager(title="Two", stake=6.0, price=0.6)],
        duplicates=[Wager(title="Seen", stake=1.0, price=0.5)],
        skipped=[SkippedRow(4, "a sell - settle the matching wager instead", "f3, KX, sell")],
    )


def testThePreviewSaysWhatWillHappen(qtbot) -> None:
    dialog = ImportPreviewDialog(None, sampleResult())
    qtbot.addWidget(dialog)

    assert "fills.csv" in dialog.headlineLabel.text()
    assert "4 rows" in dialog.headlineLabel.text()
    assert "Kalshi" in dialog.headlineLabel.text()
    assert dialog.countsLabel.text() == "2 to add  ·  1 already in the book  ·  1 not understood"
    assert dialog.table.tableModel.rowCount() == 2
    assert "Line 4: a sell" in dialog.skippedEdit.toPlainText()
    assert dialog.okButton.text() == "Import 2 Wagers"
    assert dialog.okButton.isEnabled()


def testNothingToAddLeavesTheButtonOff(qtbot) -> None:
    result = ImportResult(path=Path("empty.csv"))
    dialog = ImportPreviewDialog(None, result)
    qtbot.addWidget(dialog)

    assert dialog.okButton.text() == "Import 0 Wagers"
    assert not dialog.okButton.isEnabled()
    assert dialog.countsLabel.text() == "0 to add"
    assert not dialog.skippedEdit.isVisibleTo(dialog)
    assert "no single platform" in dialog.headlineLabel.text()


def testOneWagerIsSingular(qtbot) -> None:
    result = ImportResult(path=Path("one.csv"), toAdd=[Wager(title="Only", stake=1.0, price=0.5)])
    dialog = ImportPreviewDialog(None, result)
    qtbot.addWidget(dialog)

    assert dialog.okButton.text() == "Import 1 Wager"
