"""The main window's size and position, restored at the next start.

Kept as Qt's own geometry blob: restoring it checks the saved position
against the screens that exist now, so a window last used on a monitor that
is no longer attached comes back on screen instead of somewhere invisible.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray

from wagerBook.services import settingsService

geometryKey = "window/geometry"


def loadGeometry() -> QByteArray | None:
    value = settingsService.openSettings().value(geometryKey)
    return value if isinstance(value, QByteArray) and not value.isEmpty() else None


def saveGeometry(state: QByteArray) -> None:
    settingsService.writeValue(geometryKey, state)
