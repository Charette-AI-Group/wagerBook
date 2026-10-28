"""Tests for the full-width tab widget, and how it shows which tab is open."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette, QStandardItemModel
from PySide6.QtWidgets import QTableView, QVBoxLayout, QWidget

from wagerBook.ui import tabTheme
from wagerBook.ui.widgets import fullWidthTabWidget, tabStyling
from wagerBook.ui.widgets.fullWidthTabWidget import FullWidthTabWidget


def tabsFillHalves(tabWidget: FullWidthTabWidget) -> bool:
    tabBar = tabWidget.tabBar()
    share = tabWidget.width() // tabBar.count()
    return all(
        abs(tabBar.tabRect(i).width() - share) <= 1 for i in range(tabBar.count())
    )


def rule(style: str, selector: str) -> str:
    """What one rule of a stylesheet declares."""
    return style.split(selector, 1)[1].split("}", 1)[0]


def withTabs(qtbot, *titles: str) -> FullWidthTabWidget:
    tabWidget = FullWidthTabWidget()
    qtbot.addWidget(tabWidget)
    for title in titles or ("First", "Second"):
        tabWidget.addTab(QWidget(), title)
    return tabWidget


def testTabsShareWidthEqually(qtbot) -> None:
    tabWidget = withTabs(qtbot)
    tabWidget.resize(600, 400)
    tabWidget.show()

    qtbot.waitUntil(lambda: tabsFillHalves(tabWidget), timeout=5000)


def testTabsKeepEqualShareAfterResize(qtbot) -> None:
    tabWidget = withTabs(qtbot)
    tabWidget.resize(600, 400)
    tabWidget.show()
    qtbot.waitUntil(lambda: tabsFillHalves(tabWidget), timeout=5000)

    tabWidget.resize(840, 400)

    qtbot.waitUntil(lambda: tabsFillHalves(tabWidget), timeout=5000)


def testThreeTabsShareThirds(qtbot) -> None:
    tabWidget = withTabs(qtbot, "One", "Two", "Three")
    tabWidget.resize(600, 400)
    tabWidget.show()

    qtbot.waitUntil(lambda: tabsFillHalves(tabWidget), timeout=5000)


def testTheLabelsStandOutFromTheRestOfTheInterface(qtbot) -> None:
    tabWidget = withTabs(qtbot, "Active", "History")

    font = tabWidget.tabBar().font()
    assert font.bold()
    assert font.pointSizeF() > QFont().pointSizeF()


def testTheOpenTabIsPaintedLikeThePageBelowIt(qtbot) -> None:
    """Tab and page share one surface; that is what says the page belongs to the tab.

    The bug this replaced: the open tab was darker than its page and the closed
    one matched the page, so the window read back to front.
    """
    tabWidget = withTabs(qtbot, "Active", "History")
    style = tabWidget.styleSheet()

    openTab = rule(style, "QTabBar::tab:selected {")
    # Left to Qt to resolve while painting, so the tab cannot drift from its page.
    assert "background: palette(window)" in openTab
    assert "border-bottom: 1px solid palette(window)" in openTab  # it opens into the page
    page, _ink = tabStyling.pageAndInk(tabWidget)
    accent = tabTheme.accentFor(page)
    assert f"border-top: {fullWidthTabWidget.accentBar}px solid {accent}" in openTab
    assert "font-weight: bold" in openTab

    closedTab = rule(style, "> QTabBar::tab {")
    assert "background: palette(window)" not in closedTab  # a ground of its own
    assert "font-weight: normal" in closedTab
    assert "background: palette(window)" in rule(style, "::pane {")


def testTheStyleIsScopedToThisTabWidget(qtbot) -> None:
    """Every rule names this widget's own property, so no other tabs or tables take it."""
    tabWidget = withTabs(qtbot)
    style = tabWidget.styleSheet()

    assert tabWidget.property("topLevelTabs") is True
    rules = [part.split("{", 1)[0].strip() for part in style.split("}") if "{" in part]
    assert rules and all(selector.startswith(fullWidthTabWidget.scope) for selector in rules)


def testTheDerivedTonesFollowTheApplicationsPalette(qtbot, qapp) -> None:
    """The closed tabs' ground is worked out here, so it has to follow a theme change.

    A colour no real theme uses, so this cannot pass on the palette the suite
    happens to run under. The palette is in place by the time the application
    says it changed - the colour scheme signal comes too early to read.
    """
    tabWidget = withTabs(qtbot)
    original = qapp.palette()
    try:
        palette = QPalette(original)
        palette.setColor(QPalette.ColorRole.Window, QColor("#123456"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#ffffff"))

        qapp.setPalette(palette)  # as the system does when it switches theme
        qtbot.wait(20)

        ground = tabStyling.blend(
            QColor("#123456"), QColor("#ffffff"), tabStyling.closedGround
        ).name()
        assert f"background: {ground}" in rule(tabWidget.styleSheet(), "> QTabBar::tab {")
        # A dark page takes the lifted accent, which still reads against it.
        assert tabTheme.darkAccent in rule(tabWidget.styleSheet(), "QTabBar::tab:selected {")
    finally:
        qapp.setPalette(original)


def testAnUnchangedPaletteDoesNotRebuildTheStyle(qtbot, monkeypatch) -> None:
    tabWidget = withTabs(qtbot)
    rebuilt: list[str] = []
    monkeypatch.setattr(tabWidget, "setStyleSheet", rebuilt.append)

    tabWidget.applyTheme()

    assert rebuilt == []


def testTheAccentReadsOnEitherPage() -> None:
    assert tabTheme.accentFor(QColor("#f3f3f3")) == tabTheme.lightAccent
    assert tabTheme.accentFor(QColor("#202020")) == tabTheme.darkAccent
    assert tabTheme.lightAccent != tabTheme.darkAccent


def nestedTabsWithTable() -> tuple[QWidget, FullWidthTabWidget, QTableView]:
    parent = QWidget()
    layout = QVBoxLayout(parent)
    tabWidget = FullWidthTabWidget()
    table = QTableView()
    table.setModel(QStandardItemModel(2, 2))
    tabWidget.addTab(table, "Active")
    layout.addWidget(tabWidget)
    return parent, tabWidget, table


def testAThemeSwitchReachesTheTablesUnderTheTabs(qtbot, qapp, observableColorScheme) -> None:
    """The regression: with the tabs styled, Qt stopped handing palette changes
    to a nested tab widget, and Help > Theme > Light left the tables dark in a
    light window. Only a real scheme change shows it, so this skips on the
    offscreen plugin and runs under a plain `pytest` on Windows."""
    if not observableColorScheme:
        pytest.skip("this platform plugin does not report a forced colour scheme")
    hints = qapp.styleHints()
    hints.setColorScheme(Qt.ColorScheme.Dark)
    parent, _tabWidget, table = nestedTabsWithTable()
    qtbot.addWidget(parent)
    parent.show()
    qtbot.wait(200)

    for scheme in (Qt.ColorScheme.Light, Qt.ColorScheme.Dark, Qt.ColorScheme.Light):
        hints.setColorScheme(scheme)
        qtbot.waitUntil(
            lambda: table.palette().base().color() == qapp.palette().base().color(),
            timeout=3000,
        )


def testAThemeSwitchRestylesTheTabsForTheNewPage(qtbot, qapp, observableColorScheme) -> None:
    """Help > Theme: the closed tabs' ground and the accent follow the new page."""
    if not observableColorScheme:
        pytest.skip("this platform plugin does not report a forced colour scheme")
    hints = qapp.styleHints()
    hints.setColorScheme(Qt.ColorScheme.Light)
    tabWidget = withTabs(qtbot)
    tabWidget.show()
    qtbot.wait(200)

    hints.setColorScheme(Qt.ColorScheme.Dark)

    qtbot.waitUntil(
        lambda: tabTheme.darkAccent in tabWidget.styleSheet(), timeout=3000
    )


def testRestylingLeavesNoFixedPaletteBehind(qtbot) -> None:
    """A fixed palette would stop the next theme switch reaching the tables."""
    parent, tabWidget, _table = nestedTabsWithTable()
    qtbot.addWidget(parent)

    tabWidget.applyTheme()

    assert not tabWidget.testAttribute(Qt.WidgetAttribute.WA_SetPalette)
