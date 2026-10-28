"""How the tab bar shows which tab is open - the rule 26theOneAssets uses.

The open tab is painted the colour of the page below it and opens into it,
under an accent bar along its top, in bold; the closed tabs sit back on a
ground of their own, in a lighter weight. Tab and page reading as one surface
is what says the page belongs to that tab. Before this the open tab was
painted darker than its page and the closed one matched the page exactly, so
the window read back to front.

The page's colour and the ink go in as palette(window) and palette(window-text),
which Qt resolves while painting, so an open tab can never drift from its page.
The tones derived from them have to be worked out here, so they are rebuilt
when the application says its palette changed - the colour scheme signal
arrives while the old palette is still in place, and a style built then paints
the theme just left.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from wagerBook.ui.tabTheme import accentFor

closedGround = 0.10  # how far a closed tab's ground moves from the page towards the ink
edgeStrength = 0.22  # the hairline around a tab, the same distance from the page


def blend(colour: QColor, towards: QColor, amount: float) -> QColor:
    """`colour` moved `amount` of the way towards another - one step both themes can take."""
    return QColor(
        round(colour.red() * (1 - amount) + towards.red() * amount),
        round(colour.green() * (1 - amount) + towards.green() * amount),
        round(colour.blue() * (1 - amount) + towards.blue() * amount),
    )


def pageAndInk(widget: QWidget) -> tuple[QColor, QColor]:
    """What the page is painted with, from the application's palette rather than the widget's.

    A widget inside a window is still carrying the old colours while a theme
    change is being delivered.
    """
    application = QApplication.instance()
    palette = application.palette() if application is not None else widget.palette()
    return (palette.color(QPalette.ColorRole.Window),
            palette.color(QPalette.ColorRole.WindowText))


def styleKey(widget: QWidget) -> tuple[str, str]:
    """What a style was built from, so repeating an unchanged palette costs nothing."""
    page, ink = pageAndInk(widget)
    return page.name(), ink.name()


def tabStyleSheet(widget: QWidget, scope: str, accentBar: int, padding: str) -> str:
    """`scope` is the selector that keeps this style to one level of tabs."""
    page, ink = pageAndInk(widget)
    closed = blend(page, ink, closedGround).name()
    edge = blend(page, ink, edgeStrength).name()
    accent = accentFor(page)
    return (
        f"{scope}::pane {{"
        "background: palette(window);"
        f"border: 1px solid {edge};"
        "top: -1px;"  # the open tab's bottom edge opens into the page
        "}"
        f"{scope} > QTabBar::tab {{"
        f"background: {closed};"
        "color: palette(window-text);"
        f"border: 1px solid {edge};"
        "border-bottom: none;"
        "font-weight: normal;"
        f"padding: {padding};"
        "}"
        f"{scope} > QTabBar::tab:selected {{"
        "background: palette(window);"
        "color: palette(window-text);"
        f"border-top: {accentBar}px solid {accent};"
        "border-bottom: 1px solid palette(window);"
        "font-weight: bold;"
        "margin-bottom: -1px;"
        "}"
    )
