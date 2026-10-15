"""Show what an import would add before any of it reaches the book."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from wagerBook.services.importService import ImportResult
from wagerBook.ui.wagers.wagerColumns import previewColumns
from wagerBook.ui.wagers.wagerTable import WagerTable


def countsText(result: ImportResult) -> str:
    parts = [f"{len(result.toAdd)} to add"]
    if result.duplicates:
        parts.append(f"{len(result.duplicates)} already in the book")
    if result.skipped:
        parts.append(f"{len(result.skipped)} not understood")
    return "  ·  ".join(parts)


def skippedText(result: ImportResult) -> str:
    return "\n".join(
        f"Line {row.line}: {row.reason}    [{row.text}]" for row in result.skipped
    )


class ImportPreviewDialog(QDialog):
    def __init__(self, parent: QWidget | None, result: ImportResult) -> None:
        super().__init__(parent)
        self.result = result
        self.setWindowTitle("Import Wagers")
        self.setMinimumSize(900, 520)

        platform = str(result.platform) if result.platform else "no single platform"
        self.headlineLabel = QLabel(
            f"<b>{result.path.name}</b> — {result.rowCount} rows, read as {platform}"
        )
        self.countsLabel = QLabel(countsText(result))

        self.table = WagerTable(previewColumns)
        self.table.setWagers(result.toAdd)

        self.skippedLabel = QLabel("Rows left out, and why:")
        self.skippedEdit = QPlainTextEdit(skippedText(result))
        self.skippedEdit.setReadOnly(True)
        self.skippedEdit.setMaximumHeight(140)
        hasSkipped = bool(result.skipped)
        self.skippedLabel.setVisible(hasSkipped)
        self.skippedEdit.setVisible(hasSkipped)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.okButton = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        count = len(result.toAdd)
        self.okButton.setText(f"Import {count} Wager{'' if count == 1 else 's'}")
        self.okButton.setEnabled(count > 0)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.headlineLabel)
        layout.addWidget(self.countsLabel)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.skippedLabel)
        layout.addWidget(self.skippedEdit)
        layout.addWidget(self.buttons)


def confirmImport(parent: QWidget | None, result: ImportResult) -> bool:
    """Show the preview; True when the user chose to import."""
    dialog = ImportPreviewDialog(parent, result)
    return dialog.exec() == QDialog.DialogCode.Accepted
