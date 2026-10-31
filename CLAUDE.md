# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Runs on Windows and Linux, with a local virtual environment (`.venv`). Dependencies: matplotlib, openpyxl; the GUI uses Tkinter (on Debian/Ubuntu the `python3-tk` package). On Linux the paths are `.venv/bin/...` and `run.sh` replaces `run.bat`.

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

.venv\Scripts\python main.py                                   # GUI (run.bat does the same with pythonw)
.venv\Scripts\python main.py --import FILE [FILE ...] [--bank NAME]   # import exports into mymoney.db
.venv\Scripts\python main.py --report                          # text report, all banks
.venv\Scripts\python main.py --report --bank piraeus --year 2026 --month 09
.venv\Scripts\python main.py --lang en                         # switch language (saved to settings.json)
```

There are no tests, linter config or build step. To check the GUI, start `MyMoneyApp` from a script and take screenshots with `PIL.ImageGrab`. Set `app.attributes("-topmost", True)` first, otherwise the screenshot can catch other windows. Pass `settings_file=None` so the test doesn't overwrite the user's `settings.json`, and a temporary `db_file` so it doesn't touch the user's `mymoney.db`: `MyMoneyApp(db_file, settings_file=None)`. On Linux, drive real clicks with `xdotool` under a window manager: calling the handlers directly hides X11 problems, such as a grab that fails only while a mouse button is held down.

## Architecture

The data flows one way: `loader` → `database` → `categories` → `stats` → `gui` / `main.print_report`.

- **`database.py`**: the user imports exports into the SQLite file `mymoney.db` from the GUI or with `--import`; the app reads only from there, never from `files/`. Each row of `imports` is one file and owns all of that file's rows in `transactions`, including duplicates of other files, so deleting an import brings back the rows it was hiding. De-duplication therefore happens on read (`load_transactions` → `merge_files`). A file with the same SHA-256 is refused. Amounts are stored as text so that the `Decimal`, and with it `tx_key`, stays exactly the same. Categories, keywords and manual choices are also here, not in files. `PRAGMA user_version` tracks one-off steps: 1 = default categories seeded (`default_categories.py`, only once, so deleted ones don't return), 2 = the old `manual_categories.json` moved in by `migrate_manual_file`.
- **`loader.py`**: `load_file` picks the format: Eurobank `.csv`, or `.xlsx` recognised by its column headers (National Bank or Piraeus). `detect_bank` suggests the bank from the format; the name saved with the import becomes `Transaction.bank`. Within one bank, `merge_files` removes rows that also appear in another file, using `_match_key` (value date, amount, first 5 alphanumeric characters of the description). Files with balances take priority. `split_transfers` pairs a debit in one bank with a matching credit in another. The pairs are removed **only from the combined view**; each bank on its own still counts them.
- **`categories.py`**: `Categorizer.from_db` reads everything from the database, and `assign`/`clear` write to it. Priority order is a manual category for that transaction, then a manual category for the same description, then the first keyword match, in category `position` order. Keywords keep their spaces (`POI ` must not become `POI`). `Λοιπά έσοδα` and `Λοιπά έξοδα` are fallbacks and `database.py` refuses to rename or delete them. Manual choices are keyed by `tx_key` (date|value_date|description|amount), not stored on the rows, so they survive deleting an import and also apply to the same transaction in another file. If you change how `loader` cleans up descriptions (e.g. `PIRAEUS_CARD_SUFFIX`, whitespace handling), the user's saved manual categories stop matching, and rows already in the database keep their old descriptions until they are imported again.
- **`stats.py`**: `compute()` builds a `Stats` object. Amounts are `Decimal` and expenses are stored as positive numbers. A positive amount counts as income only if its category is an income category (`is_income` in the `categories` table, plus `"Λοιπά έσοδα"`). Otherwise it is a refund and lowers that category's expenses.
- **`gui.py`**: on a language or theme change, `_rebuild()` destroys and rebuilds the whole window. It keeps the year/month/bank filters and the selected tab in a language-neutral form. New widgets must be created in the `_build_*` methods, so that they survive the rebuild. `CategoriesDialog` manages categories and saves its form when the selection changes or the window closes. The bank selector is `IconDropdown`, a list shown in a pop-up `Treeview`. A `Combobox` cannot show images, and native Windows menus ignore the theme colours. Modal dialogs open through `run_modal`, because on X11 a grab can fail until the window is visible.
- **`i18n.py`**: every user-visible string goes through `t(key)`. `STRINGS` maps each key to a `(Greek, English)` tuple. Money formatting (`fmt_money`/`stats.fmt`) also depends on the language. Category names are user data and are not translated.
- **`theme.py`**: colours come from `theme.palette()` (imported as `colors()` in `gui.py`). Never hard-code colours, and get fonts from `theme.font()` because Segoe UI exists only on Windows. On Windows the light theme uses the native `vista` ttk theme; the dark theme, and both themes on Linux, are built on `clam`, because `vista` ignores custom colours and exists only on Windows. ttk style settings apply per ttk theme, so `theme.apply()` sets all of them again each time.
- **`settings.py`**: `settings.json` holds `language` and `theme`. Use `settings.update()`, which changes only the keys it is given, so saving one setting doesn't erase the other.

## Conventions

- Comments and docstrings are in Greek. The README is in English.
- `mymoney.db`, `manual_categories.json`, `settings.json` and the bank exports in `files/` are personal data and are git-ignored. Never commit them.
- To add a bank, follow the README: import its files under a new bank name, add an optional `bank.<name>` entry to `STRINGS` and an optional 20×20 logo at `mymoney/assets/banks/<name>.png`, and if the format is new, add a row parser next to `_nbg_row` / `_piraeus_row` and detect it in `_xlsx_format`.
