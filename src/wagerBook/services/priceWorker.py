"""Background thread for Update Prices.

One request per market, each allowed several seconds, would freeze the
window for the length of the run if it happened on the interface thread.
The worker is handed copies of what it needs and hands back a result; it
never touches the book, so nothing is shared between threads.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from wagerBook.services.priceService import PriceRequest, PriceService


class PriceWorker(QThread):
    # A PriceUpdate: the quotes, the wagers skipped and why, and when.
    finishedUpdate = Signal(object)

    def __init__(
        self,
        requests: list[PriceRequest],
        priceService: PriceService | None = None,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self.requests = list(requests)
        self.priceService = priceService or PriceService()

    def run(self) -> None:
        self.finishedUpdate.emit(self.priceService.updateAll(self.requests))
