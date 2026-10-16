"""A single wager on a binary prediction market - plain Python, no Qt.

Kalshi and Polymarket US both sell contracts that pay $1 if the side you
bought is right and nothing otherwise. The price per contract, between 0 and
1, is what the market thinks the chance of that side is, so one shape covers
both platforms: you pay `stake` for `contracts` at `price`, and the most you
can get back is one dollar per contract.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class Platform(StrEnum):
    kalshi = "Kalshi"
    polymarket = "Polymarket"


class Side(StrEnum):
    yes = "Yes"
    no = "No"


class Status(StrEnum):
    active = "Active"
    won = "Won"
    lost = "Lost"
    sold = "Sold"  # position closed early, before the market resolved
    voided = "Voided"  # market cancelled; the stake came back


closedStatuses = (Status.won, Status.lost, Status.sold, Status.voided)

# Each contract pays this if the side bought turns out right.
contractPayout = 1.0


@dataclass
class Wager:
    title: str
    platform: Platform = Platform.kalshi
    side: Side = Side.yes
    stake: float = 0.0
    """Dollars paid for the position, before fees."""
    price: float = 0.5
    """Price per contract, 0 to 1: the market-implied chance of winning."""
    fees: float = 0.0
    placedOn: date = field(default_factory=date.today)
    closesOn: date | None = None
    """When the market is expected to resolve, if known."""
    category: str = ""
    ticker: str = ""
    """The market's own id or ticker, to find it again on the site."""
    notes: str = ""
    currentPrice: float | None = None
    """Latest price seen for the side held, to value an open position.
    From Update Prices it is the price the position could be sold at."""
    pricedAt: datetime | None = None
    """When currentPrice was set, so a stale price can be told from a fresh one."""
    status: Status = Status.active
    payout: float | None = None
    """Dollars received when the wager closed."""
    settledOn: date | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    # ---------------------------------------------------------- derived ----

    @property
    def contracts(self) -> float:
        return self.stake / self.price if self.price > 0 else 0.0

    @property
    def maxPayout(self) -> float:
        """What comes back if the side bought is right."""
        return self.contracts * contractPayout

    @property
    def maxProfit(self) -> float:
        return self.maxPayout - self.stake - self.fees

    @property
    def maxReturn(self) -> float:
        """Profit if won, as a fraction of the stake."""
        return self.maxProfit / self.stake if self.stake > 0 else 0.0

    @property
    def markValue(self) -> float | None:
        """What the open position is worth at the last price seen."""
        if self.currentPrice is None:
            return None
        return self.contracts * self.currentPrice

    @property
    def isActive(self) -> bool:
        return self.status == Status.active

    @property
    def isClosed(self) -> bool:
        return self.status in closedStatuses

    @property
    def realizedProfit(self) -> float | None:
        """Net result once closed: what came back less what went in."""
        if not self.isClosed or self.payout is None:
            return None
        return self.payout - self.stake - self.fees

    def expectedPayout(self, status: Status) -> float:
        """What a settlement of this kind normally pays, as a starting point."""
        if status == Status.won:
            return self.maxPayout
        if status == Status.voided:
            return self.stake
        if status == Status.sold and self.markValue is not None:
            return self.markValue
        return 0.0

    # ------------------------------------------------------ persistence ----

    def toDict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "platform": str(self.platform),
            "side": str(self.side),
            "stake": self.stake,
            "price": self.price,
            "fees": self.fees,
            "placedOn": self.placedOn.isoformat(),
            "closesOn": self.closesOn.isoformat() if self.closesOn else None,
            "category": self.category,
            "ticker": self.ticker,
            "notes": self.notes,
            "currentPrice": self.currentPrice,
            "pricedAt": self.pricedAt.isoformat(timespec="seconds") if self.pricedAt else None,
            "status": str(self.status),
            "payout": self.payout,
            "settledOn": self.settledOn.isoformat() if self.settledOn else None,
        }

    @classmethod
    def fromDict(cls, data: dict[str, object]) -> Wager:
        def optionalDate(value: object) -> date | None:
            return date.fromisoformat(str(value)) if value else None

        def optionalFloat(value: object) -> float | None:
            return None if value is None else float(value)  # type: ignore[arg-type]

        def optionalMoment(value: object) -> datetime | None:
            return datetime.fromisoformat(str(value)) if value else None

        return cls(
            id=str(data.get("id") or uuid.uuid4().hex),
            title=str(data.get("title", "")),
            platform=Platform(str(data.get("platform", Platform.kalshi))),
            side=Side(str(data.get("side", Side.yes))),
            stake=float(data.get("stake", 0.0)),  # type: ignore[arg-type]
            price=float(data.get("price", 0.5)),  # type: ignore[arg-type]
            fees=float(data.get("fees", 0.0)),  # type: ignore[arg-type]
            placedOn=optionalDate(data.get("placedOn")) or date.today(),
            closesOn=optionalDate(data.get("closesOn")),
            category=str(data.get("category", "")),
            ticker=str(data.get("ticker", "")),
            notes=str(data.get("notes", "")),
            currentPrice=optionalFloat(data.get("currentPrice")),
            pricedAt=optionalMoment(data.get("pricedAt")),
            status=Status(str(data.get("status", Status.active))),
            payout=optionalFloat(data.get("payout")),
            settledOn=optionalDate(data.get("settledOn")),
        )
