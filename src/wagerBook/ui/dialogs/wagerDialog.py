"""Add or edit a wager: what was bought, for how much, at what price."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QWidget,
)

from wagerBook import appConfig
from wagerBook.models.wager import Platform, Side, Status, Wager
from wagerBook.services.marketReference import looksLikeAddress, parseMarketReference
from wagerBook.ui.wagers.wagerColumns import count, money, signedMoney, signedPercent


def toQDate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


def fromQDate(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


def moneySpin(maximum: float = 10_000_000.0) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(0.0, maximum)
    spin.setDecimals(2)
    spin.setPrefix("$")
    spin.setSingleStep(1.0)
    return spin


def priceSpin() -> QDoubleSpinBox:
    """A price in percent: 40.0 means 40 cents a contract, a 40% market chance."""
    spin = QDoubleSpinBox()
    spin.setRange(0.1, 99.9)
    spin.setDecimals(1)
    spin.setSuffix(" %")
    spin.setSingleStep(1.0)
    spin.setValue(50.0)
    return spin


class WagerDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, wager: Wager | None = None) -> None:
        super().__init__(parent)
        self.original = wager
        # What the price boxes showed on opening; see keptOrTyped.
        self.shownPrice: float | None = None
        self.shownCurrent: float | None = None
        self.setWindowTitle("Edit Wager" if wager else "New Wager")
        self.setMinimumWidth(520)

        self.platformBox = QComboBox()
        self.platformBox.addItems([str(platform) for platform in Platform])

        self.categoryBox = QComboBox()
        self.categoryBox.setEditable(True)
        self.categoryBox.addItems(appConfig.wagerCategories)
        self.categoryBox.setCurrentText("")

        self.titleEdit = QLineEdit()
        self.titleEdit.setPlaceholderText("The market question, as the site words it")

        self.tickerEdit = QLineEdit()
        self.tickerEdit.setPlaceholderText(
            "Paste the market's web address, or type its ticker - needed for Update Prices"
        )
        self.tickerEdit.editingFinished.connect(self.readTickerAddress)
        self.tickerNote = QLabel()
        self.tickerNote.setVisible(False)

        self.sideBox = QComboBox()
        self.sideBox.addItems([str(side) for side in Side])

        self.priceSpin = priceSpin()
        self.stakeSpin = moneySpin()
        self.feesSpin = moneySpin()

        self.placedEdit = QDateEdit(toQDate(date.today()))
        self.placedEdit.setCalendarPopup(True)
        self.placedEdit.setDisplayFormat("yyyy-MM-dd")

        self.closesCheck = QCheckBox("Known")
        self.closesEdit = QDateEdit(toQDate(date.today()))
        self.closesEdit.setCalendarPopup(True)
        self.closesEdit.setDisplayFormat("yyyy-MM-dd")
        self.closesEdit.setEnabled(False)
        self.closesCheck.toggled.connect(self.closesEdit.setEnabled)

        self.currentCheck = QCheckBox("Known")
        self.currentSpin = priceSpin()
        self.currentSpin.setEnabled(False)
        self.currentCheck.toggled.connect(self.currentSpin.setEnabled)

        self.notesEdit = QPlainTextEdit()
        self.notesEdit.setPlaceholderText("Why this wager, what to watch for...")
        self.notesEdit.setMaximumHeight(80)

        self.summaryLabel = QLabel()
        self.summaryLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.problemLabel = QLabel()
        self.problemLabel.setStyleSheet("color: #d64545;")
        self.problemLabel.setVisible(False)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        form = QFormLayout(self)
        form.addRow("Platform", self.platformBox)
        form.addRow("Category", self.categoryBox)
        form.addRow("Title", self.titleEdit)
        form.addRow("Ticker / Market Id", self.tickerEdit)
        form.addRow("", self.tickerNote)
        form.addRow("Side", self.sideBox)
        form.addRow("Price (Chance Of Winning)", self.priceSpin)
        form.addRow("Stake", self.stakeSpin)
        form.addRow("Fees", self.feesSpin)
        form.addRow("Placed On", self.placedEdit)
        form.addRow("Closes On", self.withCheck(self.closesCheck, self.closesEdit))
        form.addRow("Current Price", self.withCheck(self.currentCheck, self.currentSpin))
        form.addRow("Notes", self.notesEdit)
        form.addRow("", self.summaryLabel)
        form.addRow("", self.problemLabel)
        form.addRow(self.buttons)

        for spin in (self.priceSpin, self.stakeSpin, self.feesSpin, self.currentSpin):
            spin.valueChanged.connect(self.refreshSummary)
        self.currentCheck.toggled.connect(self.refreshSummary)

        if wager is not None:
            self.loadWager(wager)
        self.refreshSummary()
        self.titleEdit.setFocus()

    @staticmethod
    def withCheck(check: QCheckBox, widget: QWidget) -> QWidget:
        holder = QWidget()
        layout = QHBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(check)
        layout.addWidget(widget, 1)
        return holder

    def loadWager(self, wager: Wager) -> None:
        self.platformBox.setCurrentText(str(wager.platform))
        self.categoryBox.setCurrentText(wager.category)
        self.titleEdit.setText(wager.title)
        self.tickerEdit.setText(wager.ticker)
        self.sideBox.setCurrentText(str(wager.side))
        self.priceSpin.setValue(wager.price * 100)
        self.shownPrice = self.priceSpin.value()
        self.stakeSpin.setValue(wager.stake)
        self.feesSpin.setValue(wager.fees)
        self.placedEdit.setDate(toQDate(wager.placedOn))
        if wager.closesOn is not None:
            self.closesCheck.setChecked(True)
            self.closesEdit.setDate(toQDate(wager.closesOn))
        if wager.currentPrice is not None:
            self.currentCheck.setChecked(True)
            self.currentSpin.setValue(wager.currentPrice * 100)
            self.shownCurrent = self.currentSpin.value()
        self.notesEdit.setPlainText(wager.notes)

    def readTickerAddress(self) -> None:
        """A pasted web address becomes the ticker it names, and sets the platform."""
        text = self.tickerEdit.text().strip()
        if not looksLikeAddress(text):
            return
        reference = parseMarketReference(text)
        if reference is None or reference.platform is None:
            self.tickerNote.setText(
                "That address is not a Kalshi or Polymarket market. Paste the address of the"
                " market's own page."
            )
            self.tickerNote.setVisible(True)
            return
        self.tickerEdit.setText(reference.identifier)
        self.platformBox.setCurrentText(str(reference.platform))
        self.tickerNote.setText(f"Read from the {reference.platform} address.")
        self.tickerNote.setVisible(True)

    @staticmethod
    def keptOrTyped(original: float | None, shown: float | None, typedPercent: float) -> float:
        """The spin box shows a tenth of a percent; an untouched price keeps every digit.

        `shown` is what the box displayed when the form opened - read back from it,
        since its rounding of a half (38.25) need not match Python's. Without this,
        opening an imported wager and pressing OK would round 0.396271 to 0.396
        and move its Max Win.
        """
        if original is not None and shown is not None and abs(typedPercent - shown) < 1e-9:
            return original
        return typedPercent / 100

    def currentPriceAndTime(self) -> tuple[float | None, datetime | None]:
        """A fetched price left alone keeps its time; one typed in counts as entered by hand."""
        if not self.currentCheck.isChecked():
            return None, None
        base = self.original
        before = base.currentPrice if base else None
        price = self.keptOrTyped(before, self.shownCurrent, self.currentSpin.value())
        unchanged = before is not None and price == before
        return price, (base.pricedAt if unchanged and base else None)

    def wager(self) -> Wager:
        """The wager as the form describes it; settlement fields are kept as they were."""
        base = self.original
        currentPrice, pricedAt = self.currentPriceAndTime()
        return Wager(
            id=base.id if base else uuid.uuid4().hex,
            title=self.titleEdit.text().strip(),
            platform=Platform(self.platformBox.currentText()),
            side=Side(self.sideBox.currentText()),
            stake=self.stakeSpin.value(),
            price=self.keptOrTyped(
                base.price if base else None, self.shownPrice, self.priceSpin.value()
            ),
            fees=self.feesSpin.value(),
            placedOn=fromQDate(self.placedEdit.date()),
            closesOn=fromQDate(self.closesEdit.date()) if self.closesCheck.isChecked() else None,
            category=self.categoryBox.currentText().strip(),
            ticker=self.tickerEdit.text().strip(),
            notes=self.notesEdit.toPlainText().strip(),
            currentPrice=currentPrice,
            pricedAt=pricedAt,
            status=base.status if base else Status.active,
            payout=base.payout if base else None,
            settledOn=base.settledOn if base else None,
        )

    def problem(self) -> str | None:
        if not self.titleEdit.text().strip():
            return "Give the wager a title."
        if self.stakeSpin.value() <= 0:
            return "The stake has to be more than nothing."
        return None

    def refreshSummary(self) -> None:
        wager = self.wager()
        parts = [
            f"Contracts {count(wager.contracts)}",
            f"Max win {money(wager.maxPayout)}",
            f"Profit if won {signedMoney(wager.maxProfit)} ({signedPercent(wager.maxReturn)})",
        ]
        if wager.markValue is not None:
            parts.append(f"Worth now {money(wager.markValue)}")
        self.summaryLabel.setText("  ·  ".join(parts))

    def accept(self) -> None:
        # Pasting and pressing Enter can reach here before the box loses focus.
        self.readTickerAddress()
        problem = self.problem()
        if problem:
            self.problemLabel.setText(problem)
            self.problemLabel.setVisible(True)
            return
        super().accept()


def editWager(parent: QWidget | None, wager: Wager | None = None) -> Wager | None:
    """Run the dialog; the wager as entered, or None if cancelled."""
    dialog = WagerDialog(parent, wager)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.wager()
    return None
