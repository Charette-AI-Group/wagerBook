"""A sortable table of wagers that knows which wager is selected.

A selection lasts only while it is being used. A click anywhere else in the
window - another control, the blank space under the last row - lets it go,
so a row picked for an edit or just added does not stay lit long after.
Buttons that act on the selected row are named with `keepSelectionFor`, or
pressing one would clear the row it is about to act on.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, QObject, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QTableView,
    QWidget,
)

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

        # Widgets that use the selection, so pressing them keeps it.
        self.selectionKeepers: list[QWidget] = []
        # Every press in the app passes through here first; see eventFilter.
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def keepSelectionFor(self, widgets: list[QWidget]) -> None:
        """Pressing any of these leaves the selected row selected."""
        self.selectionKeepers.extend(widgets)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and isinstance(watched, QWidget)
            and self.selectionModel().hasSelection()
            and self.pressLetsSelectionGo(watched, event)
        ):
            self.clearHighlight()
        return False  # only watching: the press still goes where it was going

    def pressLetsSelectionGo(self, target: QWidget, event: QEvent) -> bool:
        """Whether a press on this widget is a click away from the selected row."""
        if target.window() is not self.window():
            # Another window - the edit form the row opened, say - is not "away".
            return False
        if target is self.viewport():
            # Inside the rows: only the blank space below the last one lets go.
            position = event.position().toPoint() if isinstance(event, QMouseEvent) else None
            return position is not None and not self.indexAt(position).isValid()
        if target is self or self.isAncestorOf(target):
            return False  # the headers and scroll bars: sorting or scrolling keeps the row
        return not any(
            keeper is target or keeper.isAncestorOf(target) for keeper in self.selectionKeepers
        )

    def clearHighlight(self) -> None:
        """No row selected and no current cell, so nothing on the table is lit."""
        self.selectionModel().clear()

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
