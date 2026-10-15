"""Tests for the CSV export."""

from __future__ import annotations

import csv
from datetime import date

from wagerBook.models.wager import Platform, Side, Status, Wager
from wagerBook.services.exportCsvService import csvColumns, exportCsv


def testEveryWagerBecomesARowWithDerivedNumbers(tmp_path) -> None:
    wagers = [
        Wager(
            title="Rain, \"heavy\"",
            platform=Platform.polymarket,
            side=Side.no,
            stake=25.0,
            price=0.4,
            fees=0.5,
            placedOn=date(2026, 10, 1),
        ),
        Wager(
            title="Done",
            stake=10.0,
            price=0.5,
            status=Status.won,
            payout=20.0,
            settledOn=date(2026, 10, 3),
        ),
    ]
    target = tmp_path / "book.csv"

    count = exportCsv(wagers, target)

    assert count == 2
    with target.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0].keys()) == csvColumns
    assert rows[0]["title"] == 'Rain, "heavy"'
    assert rows[0]["side"] == "No"
    assert rows[0]["contracts"] == "62.5"
    assert rows[0]["maxProfit"] == "37.0"
    assert rows[0]["realizedProfit"] == ""
    assert rows[1]["status"] == "Won"
    assert rows[1]["realizedProfit"] == "10.0"
    assert rows[1]["settledOn"] == "2026-10-03"


def testAnEmptyBookStillWritesTheHeader(tmp_path) -> None:
    target = tmp_path / "empty.csv"

    assert exportCsv([], target) == 0

    assert target.read_text(encoding="utf-8").strip() == ",".join(csvColumns)
