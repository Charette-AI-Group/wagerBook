"""Where the wagers live between sessions: one JSON file, rewritten whole.

The book is small - hundreds of rows at most - so a file read at start and
rewritten on every change is simpler than a database and can be opened in a
text editor when something looks wrong. Writes go to a temporary file first
and are swapped in, so a crash mid-write leaves the previous book intact.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path

from wagerBook.models.wager import Status, Wager

logger = logging.getLogger(__name__)

fileVersion = 1


class WagerStoreError(Exception):
    """The book could not be read or written; the message says why and where."""


class WagerStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.wagers: list[Wager] = []

    # ------------------------------------------------------------ file ----

    def load(self) -> None:
        """Read the book, or start empty when there is none yet."""
        if not self.path.exists():
            self.wagers = []
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            rows = data["wagers"] if isinstance(data, dict) else data
            self.wagers = [Wager.fromDict(row) for row in rows]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise WagerStoreError(
                f"Could not read the wager book. {exc}\n"
                f"The file is {self.path}. Fix or move it and start the app again; "
                "a missing file is replaced by an empty book."
            ) from exc

    def save(self) -> None:
        payload = {
            "version": fileVersion,
            "wagers": [wager.toDict() for wager in self.wagers],
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(payload, indent=2), encoding="utf-8", newline="\n"
            )
            os.replace(temporary, self.path)
        except OSError as exc:
            raise WagerStoreError(
                f"Could not save the wager book. {exc}\n"
                f"The file is {self.path}. The change is still shown but is not on disk."
            ) from exc
        logger.info("Saved %d wagers to %s", len(self.wagers), self.path)

    # --------------------------------------------------------- queries ----

    def active(self) -> list[Wager]:
        return [wager for wager in self.wagers if wager.isActive]

    def closed(self) -> list[Wager]:
        return [wager for wager in self.wagers if wager.isClosed]

    def find(self, wagerId: str) -> Wager:
        for wager in self.wagers:
            if wager.id == wagerId:
                return wager
        raise KeyError(wagerId)

    # --------------------------------------------------------- changes ----

    def add(self, wager: Wager) -> None:
        self.wagers.append(wager)
        self.save()

    def addMany(self, wagers: list[Wager]) -> None:
        """One write for a whole import, not one per row."""
        self.wagers.extend(wagers)
        self.save()

    def update(self, wager: Wager) -> None:
        """Replace the wager with the same id, keeping its place in the list."""
        for index, existing in enumerate(self.wagers):
            if existing.id == wager.id:
                self.wagers[index] = wager
                break
        else:
            raise KeyError(wager.id)
        self.save()

    def applyPrices(self, quotes: list[tuple[str, float, str]], pricedAt: datetime) -> int:
        """Set each wager's price and ticker from (wagerId, price, ticker); one write.

        A wager gone or closed since the update started is left alone.
        Returns how many were changed.
        """
        changed = 0
        byId = {wager.id: wager for wager in self.wagers}
        for wagerId, price, ticker in quotes:
            wager = byId.get(wagerId)
            if wager is None or not wager.isActive:
                continue
            wager.currentPrice = price
            wager.ticker = ticker
            wager.pricedAt = pricedAt
            changed += 1
        if changed:
            self.save()
        return changed

    def remove(self, wagerId: str) -> None:
        wager = self.find(wagerId)
        self.wagers.remove(wager)
        self.save()

    def settle(
        self, wagerId: str, status: Status, payout: float, settledOn: date
    ) -> Wager:
        """Close a wager with what actually came back."""
        if status == Status.active:
            raise ValueError("Settling needs a closed status.")
        wager = self.find(wagerId)
        wager.status = status
        wager.payout = payout
        wager.settledOn = settledOn
        self.save()
        return wager

    def reopen(self, wagerId: str) -> Wager:
        """Undo a settlement entered by mistake."""
        wager = self.find(wagerId)
        wager.status = Status.active
        wager.payout = None
        wager.settledOn = None
        self.save()
        return wager
