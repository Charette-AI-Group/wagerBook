"""Draw Wager Book's application icon, the way 26theOneAssets draws its own.

The icon is drawn with QPainter *at each size* rather than scaled down from
one large rendering, because a 16 px icon shrunk from 256 px is mush - its
strokes fall below a pixel and the shape stops reading. Each size thickens
its strokes and drops detail as it shrinks.

The artwork: a book cover in the app's indigo accent, with a darker spine
down its left edge. On the cover, the odds: a ring split into a green arc -
the chance of winning - and a coral arc for the rest, and in the middle a
white check mark, a wager settled as won.

    python tools/makeIcons.py

Writes ``src/wagerBook/resources/wagerBook.ico`` (16 to 256 px) and a 1024 px
PNG of the same drawing. The app finds them through ``appConfig``, never by
path.
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

# Before any QApplication exists: draw on the real platform, not offscreen.
os.environ.pop("QT_QPA_PLATFORM", None)

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / "src"))
outputDir = repo / "src" / "wagerBook" / "resources"
stem = "wagerBook"

from PySide6.QtCore import QBuffer, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

# What a .ico carries: 16 is the title bar and taskbar, 256 the extra-large
# view in Explorer; the sizes between are what Windows picks at other DPIs.
iconSizes = (16, 24, 32, 48, 64, 128, 256)

coverTop = QColor("#5B4BC4")  # the tabs' accent, lifted
coverBottom = QColor("#2E2373")
spineColour = QColor("#1F1852")
spineBand = QColor("#8F84E6")
winColour = QColor("#34D399")  # the chance of winning
restColour = QColor("#FB7185")  # the rest
checkColour = QColor("#FFFFFF")

# The share of the ring that is green: a wager taken at 62 cents.
winShare = 0.62


def roundPen(colour: QColor, width: float, cap: Qt.PenCapStyle = Qt.PenCapStyle.RoundCap) -> QPen:
    pen = QPen(QBrush(colour), width)
    pen.setCapStyle(cap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def hasSpine(size: int) -> bool:
    """Below 32 px the spine is a stripe of a pixel or two and only adds noise."""
    return size >= 32


def coverCentre(size: int) -> QPointF:
    # With a spine, the artwork sits on the cover, a little right of the tile's middle.
    shift = size * 0.06 if hasSpine(size) else 0.0
    return QPointF(size * 0.5 + shift, size * 0.5)


def drawCover(painter: QPainter, size: int) -> None:
    # Tighter corners when small, or the rounding eats the artwork.
    radius = size * (0.18 if size < 32 else 0.22)
    cover = QLinearGradient(QPointF(0, 0), QPointF(0, size))
    cover.setColorAt(0.0, coverTop)
    cover.setColorAt(1.0, coverBottom)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(cover)
    tile = QRectF(0, 0, size, size)
    painter.drawRoundedRect(tile, radius, radius)
    if not hasSpine(size):
        return
    # The spine: the tile's left strip, clipped to its rounded outline.
    outline = QPainterPath()
    outline.addRoundedRect(tile, radius, radius)
    painter.save()
    painter.setClipPath(outline)
    spineWidth = size * 0.16
    painter.setBrush(spineColour)
    painter.drawRect(QRectF(0, 0, spineWidth, size))
    # Two bands across the spine, as on a bound ledger.
    if size >= 48:
        painter.setBrush(spineBand)
        band = max(1.0, size * 0.025)
        for y in (0.22, 0.78):
            painter.drawRect(QRectF(0, size * y - band / 2, spineWidth, band))
    painter.restore()


def drawOdds(painter: QPainter, size: int) -> None:
    """The ring: green for the share bought, coral for the rest, a gap between."""
    centre = coverCentre(size)
    radius = size * (0.30 if size < 32 else 0.27)
    width = max(2.0, size * (0.15 if size < 32 else 0.11))
    box = QRectF(centre.x() - radius, centre.y() - radius, 2 * radius, 2 * radius)
    # Gaps between the arcs, in degrees; none when the ring is too thin to show one.
    gap = 0.0 if size < 24 else 14.0
    winSpan = 360.0 * winShare - gap
    restSpan = 360.0 * (1 - winShare) - gap
    # Qt measures from three o'clock, anticlockwise, in sixteenths of a degree;
    # a negative span runs clockwise. The green arc starts just after twelve.
    winStart = 90.0 - gap / 2
    restStart = winStart - winSpan - gap
    painter.setBrush(Qt.BrushStyle.NoBrush)
    cap = Qt.PenCapStyle.FlatCap if size < 24 else Qt.PenCapStyle.RoundCap
    painter.setPen(roundPen(winColour, width, cap))
    painter.drawArc(box, round(winStart * 16), round(-winSpan * 16))
    painter.setPen(roundPen(restColour, width, cap))
    painter.drawArc(box, round(restStart * 16), round(-restSpan * 16))


def drawCheck(painter: QPainter, size: int) -> None:
    if size < 24:
        return  # at 16 px the ring is the icon; a check would fill its hole
    centre = coverCentre(size)
    unit = size * 0.11
    points = [
        QPointF(centre.x() - 1.0 * unit, centre.y() + 0.05 * unit),
        QPointF(centre.x() - 0.25 * unit, centre.y() + 0.8 * unit),
        QPointF(centre.x() + 1.1 * unit, centre.y() - 0.75 * unit),
    ]
    path = QPainterPath()
    path.moveTo(points[0])
    for point in points[1:]:
        path.lineTo(point)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(roundPen(checkColour, max(1.8, size * 0.075)))
    painter.drawPath(path)


def render(size: int) -> QPixmap:
    """The icon at one size, drawn rather than scaled."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    drawCover(painter, size)
    drawOdds(painter, size)
    drawCheck(painter, size)
    painter.end()
    return pixmap


def pngBytes(pixmap: QPixmap) -> bytes:
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(buffer.data())


def packIco(images: list[tuple[int, bytes]]) -> bytes:
    """A multi-size .ico holding PNG entries.

    Written by hand rather than through Qt's writer, so every size is the one
    drawn at that size. Windows since Vista reads PNG inside an ICO, which
    keeps the 256 px entry small.
    """
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, payload = [], []
    for size, data in images:
        side = 0 if size >= 256 else size  # 0 means 256 in an ICO
        entries.append(struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset))
        payload.append(data)
        offset += len(data)
    return header + b"".join(entries) + b"".join(payload)


def main() -> int:
    application = QApplication.instance() or QApplication([])  # noqa: F841 - kept alive
    outputDir.mkdir(parents=True, exist_ok=True)
    ico = outputDir / f"{stem}.ico"
    ico.write_bytes(packIco([(size, pngBytes(render(size))) for size in iconSizes]))
    png = outputDir / f"{stem}.png"
    render(1024).save(str(png), "PNG")
    sizes = "/".join(str(size) for size in iconSizes)
    print(f"{ico.relative_to(repo)}  {ico.stat().st_size / 1024:.1f} kB  ({sizes} px)")
    print(f"{png.relative_to(repo)}  1024 px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
