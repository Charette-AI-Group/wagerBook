"""Tab widget whose tabs share the full width equally, labels centered.

These are the app's top-level switch, so their labels are larger and bolder
than the rest of the interface and the open one is marked in the accent
colour - not left to a hairline that reads as part of the background.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QFont, QPalette, QResizeEvent
from PySide6.QtWidgets import QTabBar, QTabWidget, QWidget

from wagerBook.ui.tabTheme import currentTokens, onColorSchemeChanged

labelScale = 1.15  # of the interface's own text size
underline = 3  # px under the open tab


class FullWidthTabBar(QTabBar):
    def tabSizeHint(self, index: int) -> QSize:
        size = super().tabSizeHint(index)
        tabWidget = self.parentWidget()
        if self.count() and tabWidget is not None:
            size.setWidth(tabWidget.width() // self.count())
        return size


class FullWidthTabWidget(QTabWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTabBar(FullWidthTabBar(self))
        font = QFont()
        font.setPointSizeF(font.pointSizeF() * labelScale)
        font.setWeight(QFont.Weight.DemiBold)
        self.tabBar().setFont(font)
        self.applyTheme()
        onColorSchemeChanged(self.scheduleTheme)

    def scheduleTheme(self, *_args: object) -> None:
        """Restyle once Qt has finished switching the theme, not while it is.

        The scheme signal arrives before Qt has handed the new palette round
        the window, so the work waits one turn of the event loop.
        """
        QTimer.singleShot(0, self, self.applyTheme)

    def applyTheme(self, *_args: object) -> None:
        """The open tab in ink on the surface, underlined in the accent; the rest quiet."""
        # A Qt quirk, seen in Qt 6.12 with no app code involved: a tab widget
        # inside another widget stops taking palette changes once its tab bar
        # has a style sheet, so after Help > Theme > Light the tables under it
        # stayed dark in an otherwise light window. An empty palette tells it
        # to inherit from its parent again; it fixes nothing in place, so the
        # next switch is inherited the same way.
        self.setPalette(QPalette())
        tokens = currentTokens()
        self.tabBar().setStyleSheet(
            "QTabBar::tab {"
            f"color: {tokens.secondaryInk};"
            f"background: {tokens.strip};"
            f"border: none; border-bottom: {underline}px solid {tokens.strip};"
            "padding: 5px 10px;"
            "}"
            "QTabBar::tab:hover {"
            f"color: {tokens.primaryInk};"
            "}"
            "QTabBar::tab:selected {"
            f"color: {tokens.primaryInk};"
            f"background: {tokens.surface};"
            f"border-bottom: {underline}px solid {tokens.accent};"
            "}"
        )

    def resizeEvent(self, event: QResizeEvent) -> None:
        # Tab widths derive from the widget width, so a resize must make the
        # tab bar re-query its size hints. QTabBar has no public relayout;
        # re-setting the icon size is the standard way to force one.
        super().resizeEvent(event)
        tabBar = self.tabBar()
        tabBar.setIconSize(tabBar.iconSize())
