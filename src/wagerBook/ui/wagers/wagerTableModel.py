"""Qt model over a list of wagers, one row each, columns from wagerColumns."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QColor

from wagerBook.models.wager import Wager
from wagerBook.ui.wagers.wagerColumns import Column

# Legible on both the light and the dark palette, so no PaletteChange handling.
gainColour = QColor("#2e9e5b")
lossColour = QColor("#d64545")

# Raw values, for the sort proxy.
sortRole = Qt.ItemDataRole.UserRole


class WagerTableModel(QAbstractTableModel):
    def __init__(self, columns: list[Column], parent=None) -> None:
        super().__init__(parent)
        self.columns = columns
        self.wagers: list[Wager] = []

    def setWagers(self, wagers: list[Wager]) -> None:
        self.beginResetModel()
        self.wagers = list(wagers)
        self.endResetModel()

    def wagerAt(self, row: int) -> Wager:
        return self.wagers[row]

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.wagers)

    def columnCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        return 0 if parent.isValid() else len(self.columns)

    def headerData(
        self, section: int, orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.columns[section].title
        return None

    def data(
        self, index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if not index.isValid():
            return None
        wager = self.wagers[index.row()]
        column = self.columns[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return column.text(wager)
        if role == sortRole:
            return column.value(wager)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column.numeric:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ForegroundRole and column.tone is not None:
            tone = column.tone(wager)
            if tone is not None and tone > 0:
                return gainColour
            if tone is not None and tone < 0:
                return lossColour
        if role == Qt.ItemDataRole.ToolTipRole and column.title == "Title":
            return wager.notes or wager.ticker or None
        return None
