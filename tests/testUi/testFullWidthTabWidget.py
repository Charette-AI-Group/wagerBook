"""Tests for the full-width tab widget."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QStandardItemModel
from PySide6.QtWidgets import QTableView, QVBoxLayout, QWidget

from wagerBook.ui import tabTheme
from wagerBook.ui.widgets import fullWidthTabWidget
from wagerBook.ui.widgets.fullWidthTabWidget import FullWidthTabWidget


def tabsFillHalves(tabWidget: FullWidthTabWidget) -> bool:
    tabBar = tabWidget.tabBar()
    share = tabWidget.width() // tabBar.count()
    return all(
        abs(tabBar.tabRect(i).width() - share) <= 1 for i in range(tabBar.count())
    )


def testTabsShareWidthEqually(qtbot) -> None:
    tabWidget = FullWidthTabWidget()
    qtbot.addWidget(tabWidget)
    tabWidget.addTab(QWidget(), "First")
    tabWidget.addTab(QWidget(), "Second")
    tabWidget.resize(600, 400)
    tabWidget.show()

    qtbot.waitUntil(lambda: tabsFillHalves(tabWidget), timeout=5000)


def testTabsKeepEqualShareAfterResize(qtbot) -> None:
    tabWidget = FullWidthTabWidget()
    qtbot.addWidget(tabWidget)
    tabWidget.addTab(QWidget(), "First")
    tabWidget.addTab(QWidget(), "Second")
    tabWidget.resize(600, 400)
    tabWidget.show()
    qtbot.waitUntil(lambda: tabsFillHalves(tabWidget), timeout=5000)

    tabWidget.resize(840, 400)

    qtbot.waitUntil(lambda: tabsFillHalves(tabWidget), timeout=5000)


def testTheLabelsStandOutFromTheRestOfTheInterface(qtbot) -> None:
    tabWidget = FullWidthTabWidget()
    qtbot.addWidget(tabWidget)
    tabWidget.addTab(QWidget(), "Active")

    font = tabWidget.tabBar().font()
    assert font.bold()
    assert font.pointSizeF() > QFont().pointSizeF()
    accent = tabTheme.currentTokens().accent
    style = tabWidget.tabBar().styleSheet()
    assert "QTabBar::tab:selected" in style
    assert f"border-bottom: {fullWidthTabWidget.underline}px solid {accent}" in style


def testTheTabsFollowTheTheme(qtbot, monkeypatch) -> None:
    tabWidget = FullWidthTabWidget()
    qtbot.addWidget(tabWidget)
    monkeypatch.setattr(fullWidthTabWidget, "currentTokens", lambda: tabTheme.darkTokens)

    tabWidget.applyTheme()

    style = tabWidget.tabBar().styleSheet()
    assert tabTheme.darkTokens.surface in style
    assert tabTheme.darkTokens.accent in style


def testAThemeChangeRestylesTheTabs(qtbot, qapp, observableColorScheme) -> None:
    """Help > Theme reaches the tabs through Qt's colour-scheme signal."""
    if not observableColorScheme:
        pytest.skip("this platform plugin does not report a forced colour scheme")
    tabWidget = FullWidthTabWidget()
    qtbot.addWidget(tabWidget)

    qapp.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    qtbot.waitUntil(
        lambda: tabTheme.darkTokens.surface in tabWidget.tabBar().styleSheet(), timeout=5000
    )


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
    """The regression: with the tab bar styled, Qt stopped handing palette changes
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


def testRestylingLeavesNoFixedPaletteBehind(qtbot) -> None:
    """A fixed palette would stop the next theme switch reaching the tables."""
    parent, tabWidget, _table = nestedTabsWithTable()
    qtbot.addWidget(parent)

    tabWidget.applyTheme()

    assert not tabWidget.testAttribute(Qt.WidgetAttribute.WA_SetPalette)


def testEachThemeHasItsOwnColours() -> None:
    assert tabTheme.lightTokens != tabTheme.darkTokens
    for tokens in (tabTheme.lightTokens, tabTheme.darkTokens):
        assert tokens.accent not in (tokens.surface, tokens.strip)
        assert tokens.primaryInk != tokens.secondaryInk


def testThreeTabsShareThirds(qtbot) -> None:
    tabWidget = FullWidthTabWidget()
    qtbot.addWidget(tabWidget)
    for title in ("One", "Two", "Three"):
        tabWidget.addTab(QWidget(), title)
    tabWidget.resize(600, 400)
    tabWidget.show()

    qtbot.waitUntil(lambda: tabsFillHalves(tabWidget), timeout=5000)
