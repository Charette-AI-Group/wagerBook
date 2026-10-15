"""Read wagers out of a CSV file: a site's export, or this app's own.

Neither site documents its download, and Kalshi's has changed shape more
than once, so this does not insist on one layout. It matches headers by name
against the aliases below (after lowercasing and turning spaces and dashes
into underscores), reads values leniently, and reports each row it cannot use
with a reason instead of giving up on the file.

Column mapping - any one alias per field is enough:

  platform    platform, exchange, site           ("kalshi" / "polymarket"); else
              guessed from the other headers
  title       title, market_title, market, question, event, name, description
  ticker      ticker, market_ticker, symbol, market_slug, slug, condition_id
  side        side, outcome, position_side, direction, action, type, book_side,
              event_type - any value containing yes/no, long/short, bid/ask
  action      the same columns, any value containing buy/sell, redeem/settle,
              deposit/withdraw/reward. Sells and redemptions are reported, not
              imported: settle the matching wager in the app instead
  contracts   contracts, count, count_fp, quantity, qty, shares, size
  price       price, average_price, avg_price, entry_price, entry_price_cents,
              yes_price, yes_price_dollars, price_cents, avgprice. A header
              ending in "cents", or a value above 1, is in cents. A yes_price
              on a No wager is turned round, or no_price / no_price_dollars is
              used when present
  stake       stake, cost, total_cost, usd_size, amount, usd, value_usd;
              else contracts x price
  fees        fees, fee, fee_cost, fee_cents, open_fees_cents
  placedOn    placed_on, placedon, created, created_time, time, timestamp,
              timestamp_utc, date, open_timestamp, opened_at
  closesOn    closes_on, closeson, close_date, expiration, expiration_time,
              end_date, resolves_on
  currentPrice current_price, currentprice, cur_price, curprice, last_price
  status      status, result ("won", "lost", "sold", "voided", "active")
              or market_result ("yes"/"no", compared with the side)
              or exit_price_cents (100 = won, 0 = lost, else sold)
  payout      payout, revenue_dollars, proceeds, revenue (cents)
  settledOn   settled_on, settledon, settled_time, settled, close_timestamp,
              closed_at, resolved_at, settlement_date
  category    category;  notes: notes, note, memo;  id: id (this app's export)

Kalshi settlement rows (market_result with yes_count_fp / no_count_fp and
yes_total_cost_dollars / no_total_cost_dollars) are read as closed wagers on
whichever side had contracts.
"""

from __future__ import annotations

import csv
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from wagerBook.models.wager import Platform, Side, Status, Wager

aliases: dict[str, tuple[str, ...]] = {
    "platform": ("platform", "exchange", "site"),
    "title": ("title", "market_title", "market", "question", "event", "name", "description"),
    "ticker": ("ticker", "market_ticker", "symbol", "market_slug", "slug", "condition_id"),
    "words": ("side", "outcome", "position_side", "direction", "action", "type",
              "book_side", "event_type", "outcome_side"),
    "contracts": ("contracts", "count", "count_fp", "quantity", "qty", "shares", "size"),
    "price": ("price", "average_price", "avg_price", "avgprice", "entry_price",
              "entry_price_cents", "price_cents", "yes_price", "yes_price_dollars"),
    "noPrice": ("no_price", "no_price_dollars"),
    "stake": ("stake", "cost", "total_cost", "usd_size", "amount", "usd", "value_usd"),
    "fees": ("fees", "fee", "fee_cost", "fee_cents", "open_fees_cents"),
    "placedOn": ("placed_on", "placedon", "created", "created_time", "time", "timestamp",
                 "timestamp_utc", "date", "open_timestamp", "opened_at"),
    "closesOn": ("closes_on", "closeson", "close_date", "expiration", "expiration_time",
                 "end_date", "resolves_on"),
    "currentPrice": ("current_price", "currentprice", "cur_price", "curprice", "last_price"),
    "status": ("status", "result"),
    "marketResult": ("market_result",),
    "exitPrice": ("exit_price_cents", "exit_price"),
    "payout": ("payout", "revenue_dollars", "proceeds"),
    "payoutCents": ("revenue",),
    "settledOn": ("settled_on", "settledon", "settled_time", "settled", "close_timestamp",
                  "closed_at", "resolved_at", "settlement_date"),
    "category": ("category",),
    "notes": ("notes", "note", "memo"),
    "id": ("id",),
    "yesCount": ("yes_count", "yes_count_fp"),
    "noCount": ("no_count", "no_count_fp"),
    "yesCost": ("yes_total_cost", "yes_total_cost_dollars"),
    "noCost": ("no_total_cost", "no_total_cost_dollars"),
}

kalshiHeaders = {"ticker", "market_ticker", "event_ticker", "count_fp", "yes_price",
                 "yes_price_dollars", "no_price_dollars", "entry_price_cents", "market_result",
                 "average_price", "direction"}
polymarketHeaders = {"market_title", "market_slug", "condition_id", "shares",
                     "transaction_hash", "proxy_wallet", "asset", "outcome", "curprice"}

sideWords = {"yes": Side.yes, "long": Side.yes, "bid": Side.yes, "y": Side.yes,
             "no": Side.no, "short": Side.no, "ask": Side.no, "n": Side.no}
actionWords = {"buy": "buy", "bought": "buy", "sell": "sell", "sold": "sell",
               "redeem": "redeem", "redemption": "redeem", "claim": "redeem",
               "settle": "settle", "settlement": "settle", "settled": "settle",
               "deposit": "cash", "withdraw": "cash", "withdrawal": "cash",
               "reward": "cash", "transfer": "cash"}
statusWords = {"won": Status.won, "win": Status.won, "lost": Status.lost, "loss": Status.lost,
               "lose": Status.lost, "sold": Status.sold, "voided": Status.voided,
               "void": Status.voided, "cancelled": Status.voided, "canceled": Status.voided,
               "refunded": Status.voided, "active": Status.active, "open": Status.active}

dateFormats = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
               "%m/%d/%Y %I:%M %p", "%m/%d/%Y", "%m/%d/%y", "%d %b %Y", "%b %d, %Y",
               "%b %d %Y", "%Y/%m/%d")


class ImportFileError(Exception):
    """The file as a whole could not be read; the message says why."""


class RowError(Exception):
    """One row could not be turned into a wager; the message says why."""


@dataclass(frozen=True)
class SkippedRow:
    line: int
    reason: str
    text: str


@dataclass
class ImportResult:
    path: Path
    platform: Platform | None = None
    toAdd: list[Wager] = field(default_factory=list)
    duplicates: list[Wager] = field(default_factory=list)
    skipped: list[SkippedRow] = field(default_factory=list)

    @property
    def rowCount(self) -> int:
        return len(self.toAdd) + len(self.duplicates) + len(self.skipped)


# ------------------------------------------------------------- reading ----


def normalizeHeader(name: str) -> str:
    return re.sub(r"[\s\-]+", "_", name.strip().strip('"').lower())


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def parseNumber(text: str) -> float:
    cleaned = re.sub(r"[,$\s\"']", "", text).rstrip("%")
    if cleaned in ("", "-", "nan", "none", "null"):
        raise RowError(f"'{text}' is not a number")
    try:
        return float(cleaned)
    except ValueError as exc:
        raise RowError(f"'{text}' is not a number") from exc


def parsePrice(text: str, header: str) -> float:
    value = abs(parseNumber(text))
    if header.endswith("cents") or value > 1.0 or text.strip().endswith("%"):
        value /= 100
    return value


def parseDate(text: str) -> date:
    raw = text.strip().strip('"')
    if re.fullmatch(r"\d{10,13}", raw):
        seconds = int(raw) / (1000 if len(raw) == 13 else 1)
        return datetime.fromtimestamp(seconds).date()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for pattern in dateFormats:
        try:
            return datetime.strptime(raw, pattern).date()
        except ValueError:
            continue
    raise RowError(f"'{text}' is not a date")


class Row:
    """One CSV row with lookups by field name rather than by header."""

    def __init__(self, raw: dict[str, str], line: int) -> None:
        self.line = line
        self.values = {normalizeHeader(key): (value or "").strip()
                       for key, value in raw.items() if key is not None}

    def header(self, fieldName: str) -> str | None:
        for alias in aliases[fieldName]:
            if self.values.get(alias):
                return alias
        return None

    def text(self, fieldName: str) -> str | None:
        header = self.header(fieldName)
        return self.values[header] if header else None

    def number(self, fieldName: str) -> float | None:
        text = self.text(fieldName)
        if text is None:
            return None
        value = parseNumber(text)
        header = self.header(fieldName) or ""
        return value / 100 if header.endswith("cents") else value

    def dateValue(self, fieldName: str) -> date | None:
        text = self.text(fieldName)
        return parseDate(text) if text else None

    def words(self) -> tuple[Side | None, str | None]:
        """The Yes/No side and the buy/sell kind, from whichever columns say."""
        side: Side | None = None
        action: str | None = None
        for alias in aliases["words"]:
            for word in tokens(self.values.get(alias, "")):
                if side is None and word in sideWords:
                    side = sideWords[word]
                if action is None and word in actionWords:
                    action = actionWords[word]
        return side, action

    def summary(self) -> str:
        shown = ", ".join(value for value in self.values.values() if value)[:80]
        return shown


def detectPlatform(headers: set[str], firstRow: Row | None) -> Platform | None:
    if firstRow is not None:
        named = (firstRow.text("platform") or "").lower()
        if "poly" in named:
            return Platform.polymarket
        if "kalshi" in named:
            return Platform.kalshi
    if headers & polymarketHeaders and not headers & kalshiHeaders:
        return Platform.polymarket
    if headers & kalshiHeaders:
        return Platform.kalshi
    return None


# ------------------------------------------------------- row to wager ----


def rowPlatform(row: Row, default: Platform | None) -> Platform:
    named = (row.text("platform") or "").lower()
    if "poly" in named:
        return Platform.polymarket
    if "kalshi" in named:
        return Platform.kalshi
    if default is None:
        raise RowError("no platform column, and the headers match neither site")
    return default


def kalshiSettlement(row: Row, platform: Platform) -> Wager | None:
    """A settlements row: counts on each side, the result, and the revenue."""
    result = (row.text("marketResult") or "").lower()
    if result not in ("yes", "no") or row.header("yesCount") is None:
        return None
    yesCount = row.number("yesCount") or 0.0
    noCount = row.number("noCount") or 0.0
    if yesCount <= 0 and noCount <= 0:
        raise RowError("settlement with no contracts on either side")
    side = Side.yes if yesCount > 0 else Side.no
    contracts = yesCount if side == Side.yes else noCount
    stake = (row.number("yesCost") if side == Side.yes else row.number("noCost")) or 0.0
    if stake <= 0:
        raise RowError("settlement with no cost on the side held")
    settledOn = row.dateValue("settledOn") or date.today()
    return Wager(
        title=row.text("title") or row.text("ticker") or "",
        platform=platform,
        side=side,
        stake=stake,
        price=stake / contracts,
        fees=row.number("fees") or 0.0,
        placedOn=row.dateValue("placedOn") or settledOn,
        ticker=row.text("ticker") or "",
        status=Status.won if result == str(side).lower() else Status.lost,
        payout=readPayout(row) if readPayout(row) is not None else (
            contracts if result == str(side).lower() else 0.0),
        settledOn=settledOn,
    )


def readPayout(row: Row) -> float | None:
    if row.header("payout") is not None:
        return row.number("payout")
    if row.header("payoutCents") is not None:
        return (row.number("payoutCents") or 0.0) / 100
    return None


def readPrice(row: Row, side: Side) -> float:
    header = row.header("price")
    if header is None:
        raise RowError("no price")
    price = parsePrice(row.values[header], header)
    if side == Side.no and header.startswith("yes_price"):
        noHeader = row.header("noPrice")
        price = parsePrice(row.values[noHeader], noHeader) if noHeader else 1.0 - price
    if not 0.0 < price < 1.0:
        raise RowError(f"price {price:g} is not between 0 and 1")
    return price


def readCurrentPrice(row: Row) -> float | None:
    header = row.header("currentPrice")
    if header is None:
        return None
    price = parsePrice(row.values[header], header)
    return price if 0.0 < price <= 1.0 else None


def readSettlement(row: Row, wager: Wager) -> None:
    """Fill in the closed state when the row carries one."""
    status: Status | None = None
    statusText = row.text("status")
    if statusText:
        for word in tokens(statusText):
            if word in statusWords:
                status = statusWords[word]
                break
    result = (row.text("marketResult") or "").lower()
    if status is None and result in ("yes", "no"):
        status = Status.won if result == str(wager.side).lower() else Status.lost
    exitHeader = row.header("exitPrice")
    if status is None and exitHeader is not None:
        exitPrice = parsePrice(row.values[exitHeader], exitHeader)
        if exitPrice >= 0.999:
            status = Status.won
        elif exitPrice <= 0.001:
            status = Status.lost
        else:
            status = Status.sold
            wager.payout = wager.contracts * exitPrice
    if status is None or status == Status.active:
        return
    wager.status = status
    payout = readPayout(row)
    if payout is not None:
        wager.payout = payout
    elif wager.payout is None:
        wager.payout = wager.expectedPayout(status)
    wager.settledOn = row.dateValue("settledOn") or date.today()


def rowToWager(row: Row, default: Platform | None) -> Wager:
    platform = rowPlatform(row, default)
    settlement = kalshiSettlement(row, platform)
    if settlement is not None:
        return settlement
    side, action = row.words()
    if action == "cash":
        raise RowError("not a wager (deposit, withdrawal, reward or transfer)")
    if action == "sell":
        raise RowError("a sell - settle the matching wager in the app as Sold instead")
    if action == "redeem" or (action == "settle" and row.header("exitPrice") is None):
        raise RowError("a redemption - settle the matching wager in the app as Won instead")
    if side is None:
        raise RowError("no Yes/No side found")
    title = row.text("title") or row.text("ticker")
    if not title:
        raise RowError("no title or ticker")
    price = readPrice(row, side)
    contracts = row.number("contracts")
    stake = row.number("stake")
    if stake is None and contracts is None:
        raise RowError("no stake or contract count")
    if stake is None:
        stake = abs(contracts or 0.0) * price
    stake = abs(stake)
    if stake <= 0:
        raise RowError("stake is zero")
    wager = Wager(
        id=row.text("id") or uuid.uuid4().hex,
        title=title,
        platform=platform,
        side=side,
        stake=stake,
        price=price,
        fees=abs(row.number("fees") or 0.0),
        placedOn=row.dateValue("placedOn") or date.today(),
        closesOn=row.dateValue("closesOn"),
        category=row.text("category") or "",
        ticker=row.text("ticker") or "",
        notes=row.text("notes") or "",
        currentPrice=readCurrentPrice(row),
    )
    readSettlement(row, wager)
    return wager


# ---------------------------------------------------------- the file ----


def duplicateKey(wager: Wager) -> tuple[str, str, str, str]:
    """Same market, same side, same day: the same wager entered twice."""
    name = (wager.ticker or wager.title).strip().lower()
    return str(wager.platform), name, str(wager.side), wager.placedOn.isoformat()


def readImportFile(path: Path, existing: list[Wager]) -> ImportResult:
    """Parse the file and sort its rows into new, already-in-the-book, and unusable."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ImportFileError(f"Could not read {path}. {exc}") from exc
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ImportFileError(f"{path} is empty or has no header row.")
    headers = {normalizeHeader(name) for name in reader.fieldnames}
    rawRows = list(reader)
    rows = [Row(raw, line) for line, raw in enumerate(rawRows, start=2)]
    result = ImportResult(path=path)
    result.platform = detectPlatform(headers, rows[0] if rows else None)

    knownIds = {wager.id for wager in existing}
    knownKeys = {duplicateKey(wager) for wager in existing}
    for row in rows:
        if not any(row.values.values()):
            continue
        try:
            wager = rowToWager(row, result.platform)
        except RowError as exc:
            result.skipped.append(SkippedRow(row.line, str(exc), row.summary()))
            continue
        if wager.id in knownIds or duplicateKey(wager) in knownKeys:
            result.duplicates.append(wager)
        else:
            result.toAdd.append(wager)
    return result
