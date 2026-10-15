"""Write the whole book as CSV, for a spreadsheet or a backup."""

from __future__ import annotations

import csv
from pathlib import Path

from wagerBook.models.wager import Wager

csvColumns = [
    "id", "status", "platform", "category", "title", "ticker", "side",
    "stake", "price", "contracts", "fees", "maxPayout", "maxProfit",
    "currentPrice", "payout", "realizedProfit", "placedOn", "closesOn",
    "settledOn", "notes",
]


def csvRow(wager: Wager) -> dict[str, object]:
    row = wager.toDict()
    row["contracts"] = round(wager.contracts, 4)
    row["maxPayout"] = round(wager.maxPayout, 2)
    row["maxProfit"] = round(wager.maxProfit, 2)
    profit = wager.realizedProfit
    row["realizedProfit"] = None if profit is None else round(profit, 2)
    return {column: row.get(column) for column in csvColumns}


def exportCsv(wagers: list[Wager], path: Path) -> int:
    """Write every wager given; returns how many rows went out."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csvColumns)
        writer.writeheader()
        for wager in wagers:
            writer.writerow(csvRow(wager))
    return len(wagers)
