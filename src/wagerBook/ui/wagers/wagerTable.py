"""A sortable table of wagers that knows which wager is selected."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView, QWidget

from wagerBook.models.wager import Wager
from wagerBook.ui.wagers.wagerColumns import Column, titleColumn
from wagerBook.ui.wagers.wagerTableModel import WagerTableModel, sortRole

minTitleWidth = 320
maxTitleWidth = 640


class WagerTable(QTableView):
    # A row was double-clicked: the natural way to open it for editing.
    wagerActivated = Signal(object)
    # The selection moved; carries the Wager, or None when nothing is selected.
    selectedWagerChanged = Signal(object)

    def __init__(self, columns: list[Column], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.columns = columns
        self.tableModel = WagerTableModel(columns, self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.tableModel)
        self.proxy.setSortRole(sortRole)
        self.setModel(self.proxy)

        self.setSortingEnabled(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)

        self.doubleClicked.connect(self.onDoubleClicked)
        self.selectionModel().selectionChanged.connect(self.onSelectionChanged)

    def setWagers(self, wagers: list[Wager]) -> None:
        """Replace the rows, keeping the same wager selected when it is still there."""
        keep = self.selectedWager()
        self.tableModel.setWagers(wagers)
        self.resizeColumnsToContents()
        self.fitTitleColumn()
        if keep is not None:
            self.selectWager(keep.id)

    def fitTitleColumn(self) -> None:
        """The title is the row's identity; a stretch column squeezed by
        fourteen others to "Chiefs win Su..." is not. Give it room and let the
        table scroll sideways instead."""
        if titleColumn not in self.columns:
            return
        section = self.columns.index(titleColumn)
        width = self.columnWidth(section)
        self.setColumnWidth(section, max(minTitleWidth, min(width, maxTitleWidth)))

    def wagerAtProxyIndex(self, index: QModelIndex) -> Wager | None:
        if not index.isValid():
            return None
        return self.tableModel.wagerAt(self.proxy.mapToSource(index).row())

    def selectedWager(self) -> Wager | None:
        rows = self.selectionModel().selectedRows()
        return self.wagerAtProxyIndex(rows[0]) if rows else None

    def selectWager(self, wagerId: str) -> bool:
        for row in range(self.proxy.rowCount()):
            index = self.proxy.index(row, 0)
            wager = self.wagerAtProxyIndex(index)
            if wager is not None and wager.id == wagerId:
                self.selectRow(row)
                self.scrollTo(index)
                return True
        return False

    def onDoubleClicked(self, index: QModelIndex) -> None:
        wager = self.wagerAtProxyIndex(index)
        if wager is not None:
            self.wagerActivated.emit(wager)

    def onSelectionChanged(self, *_args) -> None:
        self.selectedWagerChanged.emit(self.selectedWager())

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            wager = self.selectedWager()
            if wager is not None:
                self.wagerActivated.emit(wager)
                return
        super().keyPressEvent(event)
