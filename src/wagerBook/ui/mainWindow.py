"""Main application window."""

from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDesktopServices,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
)

from wagerBook import appConfig
from wagerBook.services import themeService, windowStateService
from wagerBook.services.exportCsvService import exportCsv
from wagerBook.services.importService import ImportFileError, ImportResult, readImportFile
from wagerBook.services.manualWorker import ManualWorker
from wagerBook.services.wagerStore import WagerStore, WagerStoreError
from wagerBook.ui.dialogs.aboutDialog import showAbout
from wagerBook.ui.dialogs.errorDialog import showError
from wagerBook.ui.dialogs.importDialog import confirmImport
from wagerBook.ui.wagers.wagerBookView import WagerBookView
from wagerBook.ui.widgets.reportingView import ReportingView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(appConfig.windowTitle)
        # The first-run size; after that, wherever it was when last closed.
        self.resize(appConfig.defaultWindowWidth, appConfig.defaultWindowHeight)
        savedGeometry = windowStateService.loadGeometry()
        if savedGeometry is not None:
            self.restoreGeometry(savedGeometry)
        self.manualWorker: ManualWorker | None = None

        self.buildMenuBar()
        self.showStatus("Ready")

        self.store = WagerStore(appConfig.wagersFile)
        self.bookView = WagerBookView(self.store)
        self.connectView(self.bookView)
        self.setCentralWidget(self.bookView)
        self.bookView.loadBook()

    def buildMenuBar(self) -> None:
        # Menus are kept as attributes: features can extend them later, and it
        # prevents the Python wrappers from being garbage-collected.
        fileMenu = self.fileMenu = self.menuBar().addMenu("&File")

        self.newWagerAction = QAction("&New Wager...", self)
        self.newWagerAction.setShortcut(QKeySequence.StandardKey.New)
        self.newWagerAction.triggered.connect(self.onFileNewWager)
        fileMenu.addAction(self.newWagerAction)

        self.importCsvAction = QAction("&Import CSV...", self)
        self.importCsvAction.triggered.connect(self.onFileImportCsv)
        fileMenu.addAction(self.importCsvAction)

        self.exportCsvAction = QAction("&Export CSV...", self)
        self.exportCsvAction.triggered.connect(self.onFileExportCsv)
        fileMenu.addAction(self.exportCsvAction)

        fileMenu.addSeparator()

        self.exitAction = QAction("E&xit", self)
        self.exitAction.setShortcut(QKeySequence("Ctrl+Q"))
        self.exitAction.triggered.connect(self.close)
        fileMenu.addAction(self.exitAction)

        helpMenu = self.helpMenu = self.menuBar().addMenu("&Help")

        self.themeMenu = helpMenu.addMenu("&Theme")
        self.themeGroup = QActionGroup(self)
        self.themeGroup.setExclusive(True)
        self.themeActions: dict[str, QAction] = {}
        activeTheme = themeService.loadTheme()
        for theme in themeService.themeChoices:
            action = QAction(themeService.themeLabels[theme], self)
            action.setCheckable(True)
            action.setChecked(theme == activeTheme)
            action.triggered.connect(partial(self.onThemeChosen, theme))
            self.themeGroup.addAction(action)
            self.themeMenu.addAction(action)
            self.themeActions[theme] = action

        helpMenu.addSeparator()

        self.manualAction = QAction("User &Manual...", self)
        self.manualAction.setShortcut(QKeySequence.StandardKey.HelpContents)  # F1
        self.manualAction.triggered.connect(self.onHelpManual)
        helpMenu.addAction(self.manualAction)

        self.aboutAction = QAction("&About", self)
        self.aboutAction.triggered.connect(self.onHelpAbout)
        helpMenu.addAction(self.aboutAction)

    def connectView(self, view: ReportingView) -> None:
        """Wire a view's status and failures into this window.

        Call this for every view you add. Status goes to the bar, failures go
        to a dialog, and the view is spared knowing which is which.
        """
        view.statusMessage.connect(self.showStatus)
        view.errorMessage.connect(self.showError)

    def showStatus(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def showError(self, title: str, message: str) -> None:
        """Kept a method so tests can watch for it without a dialog opening."""
        showError(self, title, message)

    def onThemeChosen(self, theme: str) -> None:
        themeService.saveTheme(theme)
        themeService.applyTheme(theme)
        if theme == themeService.systemTheme:
            self.showStatus("Theme follows the Windows setting.")
        else:
            self.showStatus(f"{theme.capitalize()} theme applied.")

    def onFileNewWager(self) -> None:
        self.bookView.onAdd()

    def chooseImportPath(self) -> str:
        """A method so tests can answer without a file dialog opening."""
        path, _filter = QFileDialog.getOpenFileName(
            self, "Import CSV", "", "CSV files (*.csv);;All files (*)"
        )
        return path

    def previewImport(self, result: ImportResult) -> bool:
        """Likewise: the preview is modal, so tests answer it here."""
        return confirmImport(self, result)

    def onFileImportCsv(self) -> None:
        path = self.chooseImportPath()
        if not path:
            self.showStatus("Import cancelled.")
            return
        try:
            result = readImportFile(Path(path), self.store.wagers)
        except ImportFileError as exc:
            self.showError("Import CSV", str(exc))
            return
        if not self.previewImport(result):
            self.showStatus("Import cancelled.")
            return
        try:
            self.store.addMany(result.toAdd)
        except WagerStoreError as exc:
            self.showError("Wager Book", str(exc))
        self.bookView.refresh()
        self.showStatus(
            f"Imported {len(result.toAdd)} wagers from {Path(path).name}"
            f" ({len(result.duplicates)} already in the book, "
            f"{len(result.skipped)} rows left out)."
        )

    def chooseExportPath(self) -> str:
        """A method so tests can answer without a file dialog opening."""
        path, _filter = QFileDialog.getSaveFileName(
            self, "Export CSV", "wagers.csv", "CSV files (*.csv);;All files (*)"
        )
        return path

    def onFileExportCsv(self) -> None:
        path = self.chooseExportPath()
        if not path:
            self.showStatus("Export cancelled.")
            return
        try:
            count = exportCsv(self.store.wagers, Path(path))
        except OSError as exc:
            self.showError(
                "Export CSV",
                f"Could not write the CSV file. {exc}\n"
                f"The path was {path}. Check that the folder exists and the file "
                "is not open in another program.",
            )
            return
        self.showStatus(f"Exported {count} wagers to {path}")

    def onHelpManual(self) -> None:
        """Open the manual, preferring the published copy when there is one.

        Whether it is reachable has to be asked separately: openUrl reports
        that a browser launched, not that the page loaded. The ask can hang
        until its timeout, so it happens off this thread. With manualUrl empty
        - which is how a new app starts - the service answers no immediately
        and the local copy is used without touching the network.
        """
        if self.manualWorker is not None:
            return
        self.manualAction.setEnabled(False)
        self.showStatus("Looking for the manual...")
        worker = ManualWorker(parent=self)
        worker.resolved.connect(self.openManual)
        worker.finished.connect(self.onManualCheckFinished)
        self.manualWorker = worker
        worker.start()

    def openManual(self, publishedIsReachable: bool) -> None:
        if publishedIsReachable and QDesktopServices.openUrl(
            QUrl(appConfig.manualUrl)
        ):
            self.showStatus("The manual is opening in your browser.")
            return
        local = appConfig.manualPath
        if local.exists() and QDesktopServices.openUrl(QUrl.fromLocalFile(str(local))):
            self.showStatus(f"Opening the local copy, {local}")
            return
        # Leaving the reader with nothing is worse than making them copy a path.
        QMessageBox.information(
            self,
            "User Manual",
            "Could not open the manual. It is at:\n\n"
            f"{appConfig.manualUrl or '(nothing published)'}\n\n{local}",
        )

    def onManualCheckFinished(self) -> None:
        if self.manualWorker is not None:
            self.manualWorker.deleteLater()
            self.manualWorker = None
        self.manualAction.setEnabled(True)

    def closeEvent(self, event: QCloseEvent) -> None:
        windowStateService.saveGeometry(self.saveGeometry())
        if self.manualWorker is not None:
            # Short, but a thread running into interpreter shutdown turns a
            # clean exit into a crash.
            self.manualWorker.wait(int(appConfig.manualTimeoutSeconds * 1000) + 1000)
        super().closeEvent(event)

    def onHelpAbout(self) -> None:
        if showAbout(self):
            self.showStatus(
                "Thank you - the donation page is opening in your browser."
            )
