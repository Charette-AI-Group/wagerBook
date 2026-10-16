# Wager Book

A desktop book for wagers placed on Kalshi and Polymarket US: every open position and every
closed one, with the stake, the market-implied chance, the most it can pay, and what it
actually paid. PySide6, one JSON file, nothing sent anywhere.

![Active tab](docs/manual/active-tab.png)

## What it does

- **Active** tab: open wagers with platform, category, title, side, stake, odds,
  max win, profit and return if won, fees, current price and mark value, placed and close dates
- **History** tab: closed wagers with the result, payout, realised P&L and return
- **Add / Edit** dialog that works the contracts, max win and profit out as you type
- **Update Prices** (F5) fetches what each open wager could be sold for now - the best bid for
  the side held - from Kalshi's and Polymarket's public market data (Polymarket US first,
  polymarket.com for its own ids), off the interface thread;
  paste a market's web address into Ticker and the app reads the id and the platform from it
- **Settle** dialog that fills in the usual payout for Won, Lost, Sold or Voided and lets you
  correct it; **Reopen** for a settlement made by mistake
- Totals under each table: open exposure and max win; closed count, win rate and net P&L
- **File > Import CSV** reads a Kalshi download, a Polymarket activity export or this app's
  own CSV, previews what it will add, skips rows already in the book, and lists rows it
  could not read with the reason
- Sorting on real values, **File > Export CSV**, light/dark theme, user manual on F1
- The window reopens where it was last closed, at the same size; the Active / History tabs are
  large and the open one is underlined in the accent colour, as in the group's other apps

The user manual is in [`docs/manual/README.md`](docs/manual/README.md), with the arithmetic.

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

## Where the data lives

`%APPDATA%\Wager Book\wagers.json` — every wager, open or closed. Rewritten whole on each
change through a temporary file, so a crash mid-write leaves the previous book intact.
`settings.ini` beside it holds the theme choice and the window's last position and size.

## App icon

The icon - a book cover with the odds on it: a ring split green and coral around a check
mark - is drawn in code, like 26theOneAssets': `tools/makeIcons.py` paints it separately at
each size from 16 to 256 px and packs them into `src/wagerBook/resources/wagerBook.ico`.
Startup sets it on every window and gives the app its own Windows taskbar ID, so a window
started by `pythonw.exe` is not filed under Python. To redraw it after changing the design:

```powershell
python tools/makeIcons.py
```

## Structure

| Layer | Folder | Purpose |
|-------|--------|---------|
| Entry | `src/wagerBook/main.py` | Start `QApplication`, show main window |
| Config | `src/wagerBook/appConfig.py` | Paths, defaults, app metadata, category list |
| Models | `src/wagerBook/models/wager.py` | `Wager` dataclass and its arithmetic; `Platform`, `Side`, `Status` |
| Services | `src/wagerBook/services/wagerStore.py` | The JSON book: load, save, add, update, settle, reopen, remove |
| | `src/wagerBook/services/wagerSummary.py` | Totals for the line under each table |
| | `src/wagerBook/services/exportCsvService.py` | CSV export |
| | `src/wagerBook/services/priceService.py` | Update Prices: both sites' public APIs, the market picked from an event by the title, sell price per side; endpoints in its docstring |
| | `src/wagerBook/services/priceWorker.py` | Runs a price update off the interface thread |
| | `src/wagerBook/services/marketReference.py` | Reads a pasted Kalshi or Polymarket address into a ticker |
| | `src/wagerBook/services/importService.py` | CSV import: header aliases, lenient values, duplicate rule; the column mapping is in its docstring |
| UI | `src/wagerBook/ui/wagers/` | Column definitions, table model, table view, the Active/History book view |
| | `src/wagerBook/ui/dialogs/wagerDialog.py` | Add / edit |
| | `src/wagerBook/ui/dialogs/settleDialog.py` | Settle |
| | `src/wagerBook/ui/dialogs/importDialog.py` | Import preview |
| | `src/wagerBook/ui/mainWindow.py` | Menus, status bar, hosts the book view |

Every change goes through `WagerStore` and both tabs are redrawn from it, so there is one
truth and nothing to keep in step by hand. Services import no Qt widgets.

See `AGENTS.md` for architecture and naming conventions (for you and AI agents).

---
*Created from the Qt App Template.*
