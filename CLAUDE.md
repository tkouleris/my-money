# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Windows, with a local virtual environment (`.venv`). Dependencies: matplotlib, openpyxl; the GUI uses Tkinter.

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

.venv\Scripts\python main.py                                   # GUI (run.bat does the same with pythonw)
.venv\Scripts\python main.py --report                          # text report, all banks
.venv\Scripts\python main.py --report --bank piraeus --year 2026 --month 09
.venv\Scripts\python main.py --lang en                         # switch language (saved to settings.json)
```

There are no tests, linter config or build step. To check the GUI, start `MyMoneyApp` from a script and take screenshots with `PIL.ImageGrab`. Set `app.attributes("-topmost", True)` first, otherwise the screenshot can catch other windows. Pass `settings_file=None` so the test doesn't overwrite the user's `settings.json`.

## Architecture

The data flows one way: `loader` → `categories` → `stats` → `gui` / `main.print_report`.

- **`loader.py`**: each subfolder of `files/` is one bank, and the folder name becomes `Transaction.bank`. `load_file` picks the format: Eurobank `.csv`, or `.xlsx` recognised by its column headers (National Bank or Piraeus). Within one bank, `load_folder` removes rows that also appear in another file, using `_match_key` (value date, amount, first 5 alphanumeric characters of the description). Files with balances take priority. `split_transfers` pairs a debit in one bank with a matching credit in another. The pairs are removed **only from the combined view**; each bank on its own still counts them.
- **`categories.py`**: priority order is a manual category for that transaction, then a manual category for the same description (`manual_categories.json`), then the first keyword match in `categories.json`. Manual choices are keyed by `tx_key` (date|value_date|description|amount). If you change how `loader` cleans up descriptions (e.g. `PIRAEUS_CARD_SUFFIX`, whitespace handling), the user's saved manual categories stop matching.
- **`stats.py`**: `compute()` builds a `Stats` object. Amounts are `Decimal` and expenses are stored as positive numbers. A positive amount counts as income only if its category is an income category (`income_categories` plus `"Λοιπά έσοδα"`). Otherwise it is a refund and lowers that category's expenses.
- **`gui.py`**: on a language or theme change, `_rebuild()` destroys and rebuilds the whole window. It keeps the year/month/bank filters and the selected tab in a language-neutral form. New widgets must be created in the `_build_*` methods, so that they survive the rebuild.
- **`i18n.py`**: every user-visible string goes through `t(key)`. `STRINGS` maps each key to a `(Greek, English)` tuple. Money formatting (`fmt_money`/`stats.fmt`) also depends on the language. Category names are user data and are not translated.
- **`theme.py`**: colours come from `theme.palette()` (imported as `colors()` in `gui.py`). Never hard-code colours. The light theme uses the native `vista` ttk theme, and the dark theme is built on `clam`, because `vista` ignores custom colours. ttk style settings apply per ttk theme, so `theme.apply()` sets all of them again each time.
- **`settings.py`**: `settings.json` holds `language` and `theme`. Use `settings.update()`, which changes only the keys it is given, so saving one setting doesn't erase the other.

## Conventions

- Comments and docstrings are in Greek. The README is in English.
- `manual_categories.json`, `settings.json` and the bank exports in `files/` are personal data and are git-ignored. Never commit them.
- To add a bank, follow the README: create a folder under `files/`, add an optional `bank.<folder>` entry to `STRINGS`, and if the format is new, add a row parser next to `_nbg_row` / `_piraeus_row` and detect it in `load_xlsx`.
