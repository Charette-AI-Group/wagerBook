"""Close a wager: how it went, what came back, and when."""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QWidget,
)

from wagerBook.models.wager import Status, Wager, closedStatuses
from wagerBook.ui.dialogs.wagerDialog import fromQDate, moneySpin, toQDate
from wagerBook.ui.wagers.wagerColumns import money, signedMoney

Settlement = tuple[Status, float, date]


class SettleDialog(QDialog):
    def __init__(self, parent: QWidget | None, wager: Wager) -> None:
        super().__init__(parent)
        self.wager = wager
        self.setWindowTitle("Settle Wager")
        self.setMinimumWidth(420)

        self.outcomeBox = QComboBox()
        self.outcomeBox.addItems([str(status) for status in closedStatuses])

        self.payoutSpin = moneySpin()
        self.settledEdit = QDateEdit(toQDate(date.today()))
        self.settledEdit.setCalendarPopup(True)
        self.settledEdit.setDisplayFormat("yyyy-MM-dd")

        self.resultLabel = QLabel()
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        form = QFormLayout(self)
        form.addRow(QLabel(f"<b>{wager.title}</b>"))
        form.addRow(
            "Position",
            QLabel(f"{wager.side} at {wager.price * 100:.1f}%, staked {money(wager.stake)}"),
        )
        form.addRow("Outcome", self.outcomeBox)
        form.addRow("Received", self.payoutSpin)
        form.addRow("Settled On", self.settledEdit)
        form.addRow("Net Result", self.resultLabel)
        form.addRow(self.buttons)

        self.outcomeBox.currentTextChanged.connect(self.onOutcomeChanged)
        self.payoutSpin.valueChanged.connect(self.refreshResult)
        self.onOutcomeChanged(self.outcomeBox.currentText())

    def status(self) -> Status:
        return Status(self.outcomeBox.currentText())

    def onOutcomeChanged(self, _text: str) -> None:
        """Each outcome has a usual payout; fill it in, leave it editable."""
        self.payoutSpin.setValue(self.wager.expectedPayout(self.status()))
        self.refreshResult()

    def refreshResult(self) -> None:
        net = self.payoutSpin.value() - self.wager.stake - self.wager.fees
        self.resultLabel.setText(signedMoney(net))

    def settlement(self) -> Settlement:
        return self.status(), self.payoutSpin.value(), fromQDate(self.settledEdit.date())


def settleWager(parent: QWidget | None, wager: Wager) -> Settlement | None:
    dialog = SettleDialog(parent, wager)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.settlement()
    return None
