"""Smoke tests for the main window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

from wagerBook import appConfig
from wagerBook.models.wager import Status, Wager
from wagerBook.services import themeService, windowStateService
from wagerBook.services.importService import ImportResult
from wagerBook.ui.mainWindow import MainWindow


def testMainWindowOpens(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    mainWindow.show()

    assert mainWindow.isVisible()
    assert mainWindow.windowTitle() == "Wager Book"
    assert mainWindow.statusBar().currentMessage() == "Ready"


def testTheBookIsTheCentralWidget(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    assert mainWindow.centralWidget() is mainWindow.bookView
    assert [mainWindow.bookView.tabs.tabText(i) for i in range(2)] == ["Active", "History"]
    assert mainWindow.store.path == appConfig.wagersFile


def testMenuBarStructure(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    menuTitles = [action.text() for action in mainWindow.menuBar().actions()]
    assert menuTitles == ["&File", "&Help"]

    fileItems = [a.text() for a in mainWindow.fileMenu.actions() if not a.isSeparator()]
    assert fileItems == ["&New Wager...", "&Import CSV...", "&Export CSV...", "E&xit"]
    assert any(a.isSeparator() for a in mainWindow.fileMenu.actions())

    helpItems = [a.text() for a in mainWindow.helpMenu.actions() if not a.isSeparator()]
    assert helpItems == ["&Theme", "User &Manual...", "&About"]


def testThemeMenuOffersSystemLightDark(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    labels = [a.text() for a in mainWindow.themeMenu.actions()]
    assert labels == ["Use &System Theme", "&Light", "&Dark"]
    assert all(a.isCheckable() for a in mainWindow.themeMenu.actions())
    assert mainWindow.themeGroup.isExclusive()
    # Following Windows is the default.
    assert mainWindow.themeActions[themeService.systemTheme].isChecked()


def testChoosingDarkAppliesAndRemembersIt(qtbot, observableColorScheme) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    mainWindow.themeActions[themeService.darkTheme].trigger()

    # The window's own job: remember the choice and say so.
    assert themeService.loadTheme() == themeService.darkTheme
    assert "Dark theme applied" in mainWindow.statusBar().currentMessage()
    # Whether Qt then paints dark is only observable on some platforms.
    if observableColorScheme:
        assert themeService.currentColorScheme() == Qt.ColorScheme.Dark


def testSavedThemeIsRestoredOnNextLaunch(qtbot) -> None:
    first = MainWindow()
    qtbot.addWidget(first)
    first.themeActions[themeService.lightTheme].trigger()

    reopened = MainWindow()
    qtbot.addWidget(reopened)

    assert reopened.themeActions[themeService.lightTheme].isChecked()


def testNewWagerOpensTheAddDialog(qtbot, monkeypatch) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    monkeypatch.setattr(
        "wagerBook.ui.wagers.wagerBookView.editWager",
        lambda parent, wager: Wager(title="From the menu", stake=5.0, price=0.5),
    )

    mainWindow.newWagerAction.trigger()

    assert [w.title for w in mainWindow.store.wagers] == ["From the menu"]
    assert mainWindow.statusBar().currentMessage() == "Added: From the menu"


def testExportCsvWritesTheWholeBook(qtbot, monkeypatch, tmp_path) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    mainWindow.store.add(Wager(title="Open", stake=5.0, price=0.5))
    mainWindow.store.add(Wager(title="Done", stake=5.0, price=0.5, status=Status.lost, payout=0.0))
    target = tmp_path / "out.csv"
    monkeypatch.setattr(MainWindow, "chooseExportPath", lambda self: str(target))

    mainWindow.exportCsvAction.trigger()

    assert target.exists()
    assert "Exported 2 wagers" in mainWindow.statusBar().currentMessage()


def testACancelledExportSaysSo(qtbot, monkeypatch) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    monkeypatch.setattr(MainWindow, "chooseExportPath", lambda self: "")

    mainWindow.exportCsvAction.trigger()

    assert mainWindow.statusBar().currentMessage() == "Export cancelled."


def testAnUnwritableExportGoesToADialog(qtbot, monkeypatch, tmp_path) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    monkeypatch.setattr(
        MainWindow, "chooseExportPath", lambda self: str(tmp_path / "missing" / "out.csv")
    )
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        MainWindow, "showError", lambda self, title, message: shown.append((title, message))
    )

    mainWindow.exportCsvAction.trigger()

    assert shown and shown[0][0] == "Export CSV"
    assert "out.csv" in shown[0][1]


fixtures = Path(__file__).resolve().parents[1] / "fixtures"


def testImportAddsThePreviewedWagersOnOk(qtbot, monkeypatch) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    monkeypatch.setattr(
        MainWindow, "chooseImportPath", lambda self: str(fixtures / "kalshiFills.csv")
    )
    previewed: list[ImportResult] = []
    monkeypatch.setattr(
        MainWindow, "previewImport", lambda self, result: previewed.append(result) or True
    )

    mainWindow.importCsvAction.trigger()

    assert len(previewed) == 1 and len(previewed[0].toAdd) == 2
    assert sorted(w.ticker for w in mainWindow.store.wagers) == [
        "KXBTC-26DEC31-150K", "KXFEDCUT-26DEC"
    ]
    assert len(mainWindow.bookView.activeTable.tableModel.wagers) == 2
    message = mainWindow.statusBar().currentMessage()
    assert "Imported 2 wagers from kalshiFills.csv" in message
    assert "2 rows left out" in message
    # It reached the file, not just the window.
    assert appConfig.wagersFile.exists()


def testImportingTheSameFileAgainAddsNothing(qtbot, monkeypatch) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    monkeypatch.setattr(
        MainWindow, "chooseImportPath", lambda self: str(fixtures / "kalshiFills.csv")
    )
    monkeypatch.setattr(MainWindow, "previewImport", lambda self, result: True)

    mainWindow.importCsvAction.trigger()
    mainWindow.importCsvAction.trigger()

    assert len(mainWindow.store.wagers) == 2
    assert "Imported 0 wagers" in mainWindow.statusBar().currentMessage()
    assert "2 already in the book" in mainWindow.statusBar().currentMessage()


def testACancelledPreviewImportsNothing(qtbot, monkeypatch) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    monkeypatch.setattr(
        MainWindow, "chooseImportPath", lambda self: str(fixtures / "kalshiFills.csv")
    )
    monkeypatch.setattr(MainWindow, "previewImport", lambda self, result: False)

    mainWindow.importCsvAction.trigger()

    assert mainWindow.store.wagers == []
    assert mainWindow.statusBar().currentMessage() == "Import cancelled."


def testAnUnreadableImportGoesToADialog(qtbot, monkeypatch, tmp_path) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    monkeypatch.setattr(
        MainWindow, "chooseImportPath", lambda self: str(tmp_path / "missing.csv")
    )
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        MainWindow, "showError", lambda self, title, message: shown.append((title, message))
    )

    mainWindow.importCsvAction.trigger()

    assert shown and shown[0][0] == "Import CSV"
    assert "missing.csv" in shown[0][1]


def testACorruptBookIsReportedNotFatal(qtbot, monkeypatch) -> None:
    appConfig.wagersFile.write_text("{broken", encoding="utf-8")
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        MainWindow, "showError", lambda self, title, message: shown.append((title, message))
    )

    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    assert shown and shown[0][0] == "Wager Book"
    assert str(appConfig.wagersFile) in shown[0][1]
    assert mainWindow.store.wagers == []


def testTheWindowSavesItsGeometryOnCloseAndRestoresItNextTime(qtbot, monkeypatch) -> None:
    """Placing it is Qt's job - restoreGeometry fits it to the screens there are, and
    the offscreen test screen is smaller than the window - so this checks the hand-off."""
    first = MainWindow()
    qtbot.addWidget(first)
    first.show()
    first.close()
    saved = windowStateService.loadGeometry()
    assert saved is not None and not saved.isEmpty()
    restored: list = []
    monkeypatch.setattr(MainWindow, "restoreGeometry",
                        lambda self, state: restored.append(state) or True)

    second = MainWindow()
    qtbot.addWidget(second)

    assert restored == [saved]


def testTheFirstRunUsesTheDefaultSize(qtbot, monkeypatch) -> None:
    """No saved geometry yet, so nothing to restore and the configured size stands."""
    assert windowStateService.loadGeometry() is None
    restored: list = []
    monkeypatch.setattr(MainWindow, "restoreGeometry",
                        lambda self, state: restored.append(state) or True)

    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    assert restored == []


def testAboutOpensTheDialogAndReportsADonation(qtbot, monkeypatch) -> None:
    """The About text itself is covered in testAboutDialog."""
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    monkeypatch.setattr(
        "wagerBook.ui.mainWindow.showAbout", lambda parent: True
    )

    mainWindow.onHelpAbout()

    assert "donation page" in mainWindow.statusBar().currentMessage()


def openedUrls(monkeypatch) -> list[str]:
    """Collect what the app asked the desktop to open, and say it worked."""
    opened: list[str] = []
    monkeypatch.setattr(
        "wagerBook.ui.mainWindow.QDesktopServices.openUrl",
        lambda url: opened.append(url.toString()) or True,
    )
    return opened


def testManualHasTheStandardHelpShortcut(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    assert mainWindow.manualAction.shortcut() == QKeySequence.StandardKey.HelpContents


def testTheStubManualShipsWithTheTemplate() -> None:
    """Without it the menu item would fail the first time anybody clicked it."""
    assert appConfig.manualPath.exists()
    assert appConfig.manualPath.read_text(encoding="utf-8").strip()


def testThePublishedManualIsTheGitHubCopyOfTheLocalOne() -> None:
    """The address must point at the file that ships in the checkout."""
    assert appConfig.manualUrl == (
        "https://github.com/Charette-AI-Group/wagerBook/blob/main/docs/manual/README.md"
    )
    assert appConfig.manualUrl.startswith(appConfig.repoUrl)
    assert appConfig.manualUrl.endswith("/docs/manual/README.md")
    assert appConfig.manualPath.name == "README.md"


def testTheLocalCopyIsOpenedWhenNothingIsPublished(qtbot, monkeypatch) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    opened = openedUrls(monkeypatch)

    mainWindow.openManual(publishedIsReachable=False)

    assert len(opened) == 1
    assert opened[0].startswith("file:")
    assert opened[0].endswith("README.md")
    assert "local copy" in mainWindow.statusBar().currentMessage()


def testThePublishedCopyWinsWhenItAnswers(qtbot, monkeypatch) -> None:
    """Set manualUrl and the behaviour switches, with no other change."""
    monkeypatch.setattr(appConfig, "manualUrl", "https://example.invalid/manual")
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    opened = openedUrls(monkeypatch)

    mainWindow.openManual(publishedIsReachable=True)

    assert opened == ["https://example.invalid/manual"]
    assert "browser" in mainWindow.statusBar().currentMessage()


def testAMissingManualLeavesTheReaderAnAddress(qtbot, monkeypatch, tmp_path) -> None:
    """Nothing opened, so the path has to be readable somewhere."""
    monkeypatch.setattr(appConfig, "manualPath", tmp_path / "gone.md")
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    openedUrls(monkeypatch)
    shown: list[str] = []
    monkeypatch.setattr(
        "wagerBook.ui.mainWindow.QMessageBox.information",
        lambda parent, title, text: shown.append(text),
    )

    mainWindow.openManual(publishedIsReachable=False)

    assert shown and "gone.md" in shown[0]
    assert appConfig.manualUrl in shown[0]


def testTheCheckRunsOffTheInterfaceThread(qtbot, monkeypatch) -> None:
    """A network probe can hang until its timeout; the window must not."""
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    openedUrls(monkeypatch)

    with qtbot.waitSignal(mainWindow.manualAction.changed, timeout=5000):
        mainWindow.onHelpManual()
    # Disabled while the probe is in flight, so it cannot be started twice.
    assert not mainWindow.manualAction.isEnabled()

    assert mainWindow.manualWorker is not None
    mainWindow.manualWorker.wait(5000)
    qtbot.waitUntil(lambda: mainWindow.manualWorker is None, timeout=5000)
    assert mainWindow.manualAction.isEnabled()
