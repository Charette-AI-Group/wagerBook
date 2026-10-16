"""The colours the main tabs are drawn in, for the light and the dark theme.

The same values as the Charette AI Group's other apps (26theOneAssets), so the
tabs look alike across them: quiet ink on a grey strip for the closed tabs,
full ink on the window surface with an accent underline for the open one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


@dataclass(frozen=True)
class TabTokens:
    surface: str
    """Behind the open tab: the window's own background."""
    primaryInk: str
    """The open tab's label, and any tab under the pointer."""
    secondaryInk: str
    """The other tabs' labels."""
    strip: str
    """Behind the closed tabs."""
    accent: str
    """The line under the open tab."""


lightTokens = TabTokens(
    surface="#fcfcfb", primaryInk="#0b0b0b", secondaryInk="#52514e",
    strip="#e1e0d9", accent="#4a3aa7",
)
darkTokens = TabTokens(
    surface="#1a1a19", primaryInk="#ffffff", secondaryInk="#c3c2b7",
    strip="#2c2c2a", accent="#9085e9",
)


def currentTokens() -> TabTokens:
    dark = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    return darkTokens if dark else lightTokens


def onColorSchemeChanged(slot: Callable[..., None]) -> None:
    """Help > Theme and the Windows setting both arrive through this signal."""
    QGuiApplication.styleHints().colorSchemeChanged.connect(slot)
