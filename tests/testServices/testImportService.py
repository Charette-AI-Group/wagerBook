"""Tests for reading wagers out of the sites' CSV files and this app's own."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from wagerBook.models.wager import Platform, Side, Status, Wager
from wagerBook.services.exportCsvService import exportCsv
from wagerBook.services.importService import (
    ImportFileError,
    duplicateKey,
    normalizeHeader,
    parseDate,
    parseNumber,
    parsePrice,
    readImportFile,
)

fixtures = Path(__file__).resolve().parents[1] / "fixtures"


def byTicker(wagers: list[Wager]) -> dict[str, Wager]:
    return {wager.ticker: wager for wager in wagers}


# ------------------------------------------------------------ helpers ----


def testHeadersAreMatchedLoosely() -> None:
    assert normalizeHeader(" Market Ticker ") == "market_ticker"
    assert normalizeHeader("yes-price") == "yes_price"
    assert normalizeHeader('"Created"') == "created"


def testNumbersAcceptMoneyPunctuation() -> None:
    assert parseNumber("$1,234.50") == 1234.5
    assert parseNumber(" -40.00 ") == -40.0
    with pytest.raises(Exception):
        parseNumber("n/a")


def testPricesInCentsOrPercentBecomeFractions() -> None:
    assert parsePrice("63", "entry_price_cents") == pytest.approx(0.63)
    assert parsePrice("63", "price") == pytest.approx(0.63)
    assert parsePrice("0.63", "price") == pytest.approx(0.63)
    assert parsePrice("63%", "price") == pytest.approx(0.63)


def testDatesInTheShapesTheSitesUse() -> None:
    assert parseDate("2026-10-02T14:05:00Z") == date(2026, 10, 2)
    assert parseDate("2026-09-12T10:00:00-04:00") == date(2026, 9, 12)
    assert parseDate("10/02/2026 14:05") == date(2026, 10, 2)
    assert parseDate("10/2/2026") == date(2026, 10, 2)
    assert parseDate("2026-10-02") == date(2026, 10, 2)
    assert parseDate("1759413900") == date.fromtimestamp(1759413900)
    with pytest.raises(Exception):
        parseDate("yesterday")


# ------------------------------------------------------------- Kalshi ----


def testKalshiFillsBecomeOpenWagersAndSellsAreReported() -> None:
    result = readImportFile(fixtures / "kalshiFills.csv", [])

    assert result.platform == Platform.kalshi
    added = byTicker(result.toAdd)
    assert set(added) == {"KXFEDCUT-26DEC", "KXBTC-26DEC31-150K"}
    fed = added["KXFEDCUT-26DEC"]
    assert fed.side == Side.yes
    assert fed.price == pytest.approx(0.62)
    assert fed.stake == pytest.approx(80 * 0.62)
    assert fed.contracts == pytest.approx(80.0)
    assert fed.fees == pytest.approx(0.70)
    assert fed.placedOn == date(2026, 10, 2)
    assert fed.title == "KXFEDCUT-26DEC"
    assert fed.isActive
    # A No fill is priced on the No side, not the Yes price.
    btc = added["KXBTC-26DEC31-150K"]
    assert btc.side == Side.no
    assert btc.price == pytest.approx(0.71)
    assert btc.stake == pytest.approx(56.34 * 0.71)

    reasons = {row.line: row.reason for row in result.skipped}
    assert "sell" in reasons[4]
    assert "no stake or contract count" in reasons[5]
    assert result.duplicates == []
    assert result.rowCount == 4


def testKalshiLegacyLedgerReadsCentsAndSkipsNonTrades() -> None:
    result = readImportFile(fixtures / "kalshiLegacy.csv", [])

    assert result.platform == Platform.kalshi
    added = byTicker(result.toAdd)
    assert set(added) == {"FEDCUT-26DEC", "BTC-150K-26DEC31"}
    assert added["FEDCUT-26DEC"].price == pytest.approx(0.62)
    assert added["FEDCUT-26DEC"].stake == pytest.approx(80 * 0.62)
    assert added["FEDCUT-26DEC"].placedOn == date(2026, 10, 2)
    assert added["BTC-150K-26DEC31"].side == Side.no
    assert added["BTC-150K-26DEC31"].price == pytest.approx(0.71)
    reasons = [row.reason for row in result.skipped]
    assert any("redemption" in reason for reason in reasons)
    assert any("deposit" in reason for reason in reasons)


def testKalshiPairedPositionsCarryTheirSettlement() -> None:
    result = readImportFile(fixtures / "kalshiPositions.csv", [])

    assert result.skipped == []
    added = byTicker(result.toAdd)
    won = added["KXSHUTDOWN-26OCT01"]
    assert won.side == Side.no
    assert won.status == Status.won
    assert won.price == pytest.approx(0.55)
    assert won.fees == pytest.approx(0.80)
    assert won.payout == pytest.approx(109.0)
    assert won.placedOn == date(2026, 9, 12)
    assert won.settledOn == date(2026, 10, 1)
    lost = added["KXCPI-26SEP-3.0"]
    assert lost.status == Status.lost and lost.payout == 0.0
    sold = added["KXDODGERS-26WS"]
    assert sold.status == Status.sold
    assert sold.payout == pytest.approx(83 * 0.40)
    still = added["KXFEDCUT-26DEC"]
    assert still.isActive and still.payout is None and still.settledOn is None


def testKalshiSettlementsReadTheSideThatHeldContracts() -> None:
    result = readImportFile(fixtures / "kalshiSettlements.csv", [])

    assert result.skipped == []
    added = byTicker(result.toAdd)
    won = added["KXSHUTDOWN-26OCT01"]
    assert won.side == Side.no
    assert won.status == Status.won
    assert won.stake == pytest.approx(59.95)
    assert won.contracts == pytest.approx(109.0)
    assert won.payout == pytest.approx(109.0)
    assert won.fees == pytest.approx(0.80)
    assert won.settledOn == date(2026, 10, 1)
    lost = added["KXCPI-26SEP-3.0"]
    assert lost.side == Side.yes
    assert lost.status == Status.lost
    assert lost.stake == pytest.approx(30.15)
    assert lost.payout == 0.0


# --------------------------------------------------------- Polymarket ----


def testPolymarketActivityKeepsBuysOnly() -> None:
    result = readImportFile(fixtures / "polymarketActivity.csv", [])

    assert result.platform == Platform.polymarket
    titles = {wager.title: wager for wager in result.toAdd}
    assert set(titles) == {"Chiefs win Super Bowl LXI?", "Bitcoin above $150k on Dec 31?"}
    chiefs = titles["Chiefs win Super Bowl LXI?"]
    assert chiefs.platform == Platform.polymarket
    assert chiefs.side == Side.yes
    assert chiefs.stake == pytest.approx(100.0)
    assert chiefs.price == pytest.approx(0.18)
    assert chiefs.contracts == pytest.approx(555.56, abs=0.01)
    assert chiefs.ticker == "chiefs-win-super-bowl-lxi"
    assert chiefs.placedOn == date(2026, 9, 1)
    assert titles["Bitcoin above $150k on Dec 31?"].side == Side.no

    reasons = {row.line: row.reason for row in result.skipped}
    assert "sell" in reasons[4]
    assert "redemption" in reasons[5]
    assert "deposit" in reasons[6]
    assert "no price" in reasons[7]


# ------------------------------------------------------- own export ----


def testTheAppsOwnExportRoundTrips(tmp_path) -> None:
    wagers = [
        Wager(title="Open one", platform=Platform.polymarket, side=Side.no, stake=40.0,
              price=0.71, fees=0.0, placedOn=date(2026, 10, 10), closesOn=date(2026, 12, 31),
              category="Crypto", ticker="btc-150k", notes="Hedge", currentPrice=0.75),
        Wager(title="Closed one", platform=Platform.kalshi, side=Side.yes, stake=30.0,
              price=0.45, fees=0.4, placedOn=date(2026, 9, 20), status=Status.lost,
              payout=0.0, settledOn=date(2026, 10, 10)),
    ]
    target = tmp_path / "book.csv"
    exportCsv(wagers, target)

    result = readImportFile(target, [])

    assert result.skipped == []
    assert [wager.toDict() for wager in result.toAdd] == [wager.toDict() for wager in wagers]


def testTheAppsOwnExportIsADuplicateOfItself(tmp_path) -> None:
    wagers = [Wager(title="Mine", stake=5.0, price=0.5, placedOn=date(2026, 10, 1))]
    target = tmp_path / "book.csv"
    exportCsv(wagers, target)

    result = readImportFile(target, wagers)

    assert result.toAdd == [] and len(result.duplicates) == 1


# --------------------------------------------------------- duplicates ----


def testTheSameMarketSideAndDayIsADuplicate() -> None:
    existing = [Wager(title="Fed cuts", platform=Platform.kalshi, side=Side.yes, stake=1.0,
                      price=0.5, ticker="kxfedcut-26dec", placedOn=date(2026, 10, 2))]

    result = readImportFile(fixtures / "kalshiFills.csv", existing)

    assert [wager.ticker for wager in result.duplicates] == ["KXFEDCUT-26DEC"]
    assert [wager.ticker for wager in result.toAdd] == ["KXBTC-26DEC31-150K"]


def testADifferentDayOrSideIsNotADuplicate() -> None:
    base = Wager(title="T", ticker="X", side=Side.yes, placedOn=date(2026, 1, 1))
    otherDay = Wager(title="T", ticker="X", side=Side.yes, placedOn=date(2026, 1, 2))
    otherSide = Wager(title="T", ticker="X", side=Side.no, placedOn=date(2026, 1, 1))

    assert duplicateKey(base) != duplicateKey(otherDay)
    assert duplicateKey(base) != duplicateKey(otherSide)
    assert duplicateKey(base) == duplicateKey(Wager(title="t", ticker="x", side=Side.yes,
                                                    placedOn=date(2026, 1, 1)))


# ------------------------------------------------------------- errors ----


def testAMissingFileIsAFileError(tmp_path) -> None:
    with pytest.raises(ImportFileError) as caught:
        readImportFile(tmp_path / "nowhere.csv", [])
    assert "nowhere.csv" in str(caught.value)


def testAnEmptyFileIsAFileError(tmp_path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")

    with pytest.raises(ImportFileError):
        readImportFile(empty, [])


def testAFileNobodyRecognisesSkipsEveryRowWithAReason(tmp_path) -> None:
    odd = tmp_path / "odd.csv"
    odd.write_text("colour,shape\nred,circle\n", encoding="utf-8")

    result = readImportFile(odd, [])

    assert result.platform is None
    assert result.toAdd == []
    assert len(result.skipped) == 1
    assert "platform" in result.skipped[0].reason


def testABomAndBlankLinesAreTolerated(tmp_path) -> None:
    path = tmp_path / "bom.csv"
    path.write_text(
        "﻿platform,title,side,stake,price,placedOn\n"
        "Kalshi,Rain,Yes,10,0.5,2026-10-01\n"
        ",,,,,\n",
        encoding="utf-8",
    )

    result = readImportFile(path, [])

    assert [wager.title for wager in result.toAdd] == ["Rain"]
    assert result.skipped == []
