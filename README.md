# Wager Book

Wager Book desktop app (PySide6)

## One-time setup

```powershell
cd W:\projects\26wagerBook
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Daily workflow

```powershell
cd W:\projects\26wagerBook
.\.venv\Scripts\Activate.ps1
wager-book
```

Or without the script entry point:

```powershell
python -m wagerBook.main
```

Or just double-click **`runApp.cmd`** in the project folder (needs the one-time setup done first).

## Tests and lint

```powershell
pytest
ruff check src tests
```

## Structure

| Layer | Folder | Purpose |
|-------|--------|---------|
| Entry | `src/wagerBook/main.py` | Start `QApplication`, show main window |
| Config | `src/wagerBook/appConfig.py` | Paths, defaults, app metadata |
| UI | `src/wagerBook/ui/` | Widgets and dialogs only |
| Services | `src/wagerBook/services/` | Business logic (no Qt widgets) |
| Models | `src/wagerBook/models/` | Plain Python data types |

See `AGENTS.md` for architecture and naming conventions (for you and AI agents).

---
*Created from the Qt App Template.*
