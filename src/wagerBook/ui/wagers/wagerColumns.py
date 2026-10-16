"""What each table shows, one column at a time, and how numbers are written.

A column has a raw value for sorting and a text for display, so a table
sorted on Stake orders by dollars rather than by the string "$1,000.00".
Raw values are kept to types Qt can compare: floats, and ISO date strings.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from wagerBook.models.wager import Wager

# ---------------------------------------------------------- formatting ----


def money(value: float | None) -> str:
    if value is None:
        return ""
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def signedMoney(value: float | None) -> str:
    """Profit and loss: the sign is the point, so it is always written."""
    if value is None:
        return ""
    sign = "+" if value > 0 else "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def oddsPercent(fraction: float | None) -> str:
    """The price paid, to a thousandth of a percent: 11.685%, as the edit form shows it."""
    if fraction is None:
        return ""
    return f"{fraction * 100:.3f}%"


def percent(fraction: float | None) -> str:
    if fraction is None:
        return ""
    return f"{fraction * 100:.1f}%"


def signedPercent(fraction: float | None) -> str:
    if fraction is None:
        return ""
    sign = "+" if fraction > 0 else ""
    return f"{sign}{fraction * 100:.0f}%"


def count(value: float) -> str:
    return f"{value:,.2f}"


def dateText(value: date | None) -> str:
    return value.isoformat() if value else ""


def sortableDate(value: date | None) -> str:
    # Empty sorts first either way; ISO text orders the rest correctly.
    return value.isoformat() if value else ""


def sortableNumber(value: float | None) -> float:
    return float("-inf") if value is None else value


# ------------------------------------------------------------- columns ----


@dataclass(frozen=True)
class Column:
    title: str
    value: Callable[[Wager], object]
    """Raw value for sorting."""
    text: Callable[[Wager], str]
    numeric: bool = False
    """Right-aligned in the table."""
    tone: Callable[[Wager], float | None] | None = None
    """A number whose sign colours the cell: gains one way, losses the other."""
    tip: Callable[[Wager], str | None] | None = None
    """Shown when the pointer rests on the cell."""


def priceTip(wager: Wager) -> str | None:
    """Where the Now price came from, and how old it is."""
    if wager.currentPrice is None:
        return "No price yet. Use Update Prices (F5) once the Ticker is filled in."
    if wager.pricedAt is None:
        return "Entered by hand"
    return f"Sell price as of {wager.pricedAt:%Y-%m-%d %H:%M}"


def realizedReturn(wager: Wager) -> float | None:
    profit = wager.realizedProfit
    if profit is None or wager.stake <= 0:
        return None
    return profit / wager.stake


platformColumn = Column("Platform", lambda w: str(w.platform), lambda w: str(w.platform))
categoryColumn = Column("Category", lambda w: w.category, lambda w: w.category)
titleColumn = Column(
    "Title", lambda w: w.title, lambda w: w.title, tip=lambda w: w.notes or w.ticker or None
)
sideColumn = Column("Side", lambda w: str(w.side), lambda w: str(w.side))
stakeColumn = Column("Stake", lambda w: w.stake, lambda w: money(w.stake), numeric=True)
oddsColumn = Column("Odds", lambda w: w.price, lambda w: oddsPercent(w.price), numeric=True)
maxWinColumn = Column(
    "Max Win", lambda w: w.maxPayout, lambda w: money(w.maxPayout), numeric=True
)
profitIfWonColumn = Column(
    "Profit If Won", lambda w: w.maxProfit, lambda w: signedMoney(w.maxProfit),
    numeric=True, tone=lambda w: w.maxProfit,
)
returnIfWonColumn = Column(
    "Return", lambda w: w.maxReturn, lambda w: signedPercent(w.maxReturn), numeric=True
)
feesColumn = Column("Fees", lambda w: w.fees, lambda w: money(w.fees), numeric=True)
nowColumn = Column(
    "Now", lambda w: sortableNumber(w.currentPrice), lambda w: percent(w.currentPrice),
    numeric=True, tip=priceTip,
)
valueColumn = Column(
    "Value", lambda w: sortableNumber(w.markValue), lambda w: money(w.markValue),
    numeric=True, tip=priceTip,
)
placedColumn = Column(
    "Placed", lambda w: sortableDate(w.placedOn), lambda w: dateText(w.placedOn)
)
closesColumn = Column(
    "Closes", lambda w: sortableDate(w.closesOn), lambda w: dateText(w.closesOn)
)
resultColumn = Column("Result", lambda w: str(w.status), lambda w: str(w.status))
payoutColumn = Column(
    "Payout", lambda w: sortableNumber(w.payout), lambda w: money(w.payout), numeric=True
)
profitLossColumn = Column(
    "P&L", lambda w: sortableNumber(w.realizedProfit),
    lambda w: signedMoney(w.realizedProfit), numeric=True, tone=lambda w: w.realizedProfit,
)
realizedReturnColumn = Column(
    "Return", lambda w: sortableNumber(realizedReturn(w)),
    lambda w: signedPercent(realizedReturn(w)), numeric=True, tone=realizedReturn,
)
settledColumn = Column(
    "Settled", lambda w: sortableDate(w.settledOn), lambda w: dateText(w.settledOn)
)

# No Contracts column: each contract pays $1, so the count is Max Win in dollars
# and a second column would only repeat it. The edit form still states it.
activeColumns: list[Column] = [
    platformColumn, categoryColumn, titleColumn, sideColumn, stakeColumn, oddsColumn,
    maxWinColumn, profitIfWonColumn, returnIfWonColumn, feesColumn,
    nowColumn, valueColumn, placedColumn, closesColumn,
]

# What an import preview needs: enough to recognise each row, open or closed.
previewColumns: list[Column] = [
    platformColumn, titleColumn, sideColumn, stakeColumn, oddsColumn, maxWinColumn,
    resultColumn, payoutColumn, placedColumn, settledColumn,
]

closedColumns: list[Column] = [
    platformColumn, categoryColumn, titleColumn, sideColumn, stakeColumn, oddsColumn,
    maxWinColumn, resultColumn, payoutColumn, profitLossColumn, realizedReturnColumn,
    feesColumn, placedColumn, settledColumn,
]
