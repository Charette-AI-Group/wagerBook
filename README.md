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

**Website:** <https://charette-ai-group.github.io/wagerBook/> — screenshots, the full manual and
the downloads, built from [`docs/`](docs/).

The user manual is in [`docs/manual/README.md`](docs/manual/README.md), with the arithmetic.

## Download

Users do not need Python. [Releases](https://github.com/Charette-AI-Group/wagerBook/releases)
carry a Windows installer, a Windows portable zip and a macOS app bundle:

| File | For |
|------|-----|
| `wagerBookSetup-<version>.exe` | Windows. Per-user install, no administrator rights; adds a Start menu entry |
| `WagerBook-<version>-portable.zip` | Windows, without installing: unzip anywhere and run `WagerBook.exe` |
| `WagerBook-<version>-macos.zip` | macOS: unzip and drag `WagerBook.app` to Applications |

Your book stays in `%APPDATA%\Wager Book` (on macOS, the user's application data folder), not
in the install folder, so upgrading or uninstalling never touches your wagers.

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

## Standalone builds and releases

The release files are built by [`.github/workflows/build.yml`](.github/workflows/build.yml), the
same pipeline as 26FRWB: every push runs the tests on Windows and macOS and builds both; pushing
a version tag also publishes a GitHub Release with the builds attached.

To build them yourself:

```powershell
pip install -e ".[build]"
python tools\buildExe.py
python tools\buildInstaller.py
```

| Step | Produces | Notes |
|------|----------|-------|
| `tools/buildExe.py` on Windows | `dist\WagerBook\` | One-folder PyInstaller bundle, about 120 MB |
| `tools/buildExe.py` on macOS | `dist/WagerBook.app` | Application bundle, from the same spec |
| `tools\buildInstaller.py` | `dist\wagerBookSetup-<version>.exe` | Inno Setup 6, about 33 MB. Needs `winget install JRSoftware.InnoSetup`. Windows only |

`tools/buildExe.py` inventories what landed in the bundle - the icon, the manual, certifi's
certificate list - and then runs the built app's `--selftest report.txt`, which also builds the
window offscreen against a scratch book. A windowed build has no console, so asking it is the
only proof it starts; the script refuses to call a bundle shippable until it answers.

The certificate list matters for Update Prices: a standalone macOS build often finds no system
list, and every https request would then fail as if the price sites were down.
`services/httpsService.py` uses certifi's list everywhere, so the answer is the same from
source and from every build.

### A note for macOS users

The app bundle is **not code-signed or notarised**, so Gatekeeper will refuse it on first open
with a message about an unidentified developer. Right-click the app and choose **Open**, which
offers a button the plain double-click does not, or clear the quarantine flag:

```bash
xattr -dr com.apple.quarantine WagerBook.app
```

Signing needs a paid Apple Developer account, which this project does not have.

### Publishing a release

Tag a commit whose `appConfig.appVersion` matches. The workflow refuses a tag that disagrees,
because a release named after a version the app does not report leaves a bug report
unanswerable.

```powershell
git tag -a v0.1.0 -m "What changed in this release" ; git push origin v0.1.0
```

The tag's message becomes the release notes. `git tag` deletes lines starting with `#` by
default, so if the notes use Markdown headings, write them to a file and tag with
`--cleanup=whitespace` instead:

```powershell
git tag -a v0.1.1 --cleanup=whitespace -F notes.md ; git push origin v0.1.1
```

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

## License

[MIT](LICENSE), copyright Charette AI Group, LLC.

---
*Created from the Qt App Template.*
