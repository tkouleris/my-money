# MyMoney

A small desktop app that imports the transaction exports of your Greek bank accounts into a local database and shows income and expense statistics. You can view each bank on its own or all banks combined.

Everything runs locally. Your bank data never leaves your computer.

## Features

- Income, expenses, net result, latest balance and average daily spending
- Yearly and monthly income vs. expenses (chart + table), with average monthly spending per year
- Per-bank comparison, with a combined total
- Expenses by category, daily expenses, top merchants
- Searchable transaction list with a bank and category filter
- Automatic categorisation by keywords, plus manual categories you set from the app for one or many transactions
- Categories and keywords are managed from the app
- Transfers between your own banks are detected and left out of the combined total, so they are not counted twice
- Bank exports and categories are stored in a local SQLite database, and an import can be undone
- Overlapping exports of the same bank are de-duplicated
- A plain-text report for the terminal
- Greek (default) and English interface
- Light (default) and dark theme

## Supported banks

| Name           | Bank           | Export format                                               | Balance |
|----------------|----------------|-------------------------------------------------------------|---------|
| `eurobank`     | Eurobank       | `.csv` (`;`-separated, Greek number format)                 | yes     |
| `nationalbank` | National Bank  | `.xlsx` (`statementexport…`)                                 | yes     |
| `piraeus`      | Piraeus Bank   | `.xlsx` (Λίστα Ενοποιημένων Συναλλαγών)                     | no      |

The app tells the two `.xlsx` formats apart by their column headers, so the file names don't matter.

## Requirements

- Python 3.10 or newer, with Tkinter
- Windows or Linux

## Setup

On Windows:

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

On Linux, Tkinter and `venv` are usually separate packages, so install them first. On Debian and Ubuntu:

```sh
sudo apt install python3-venv python3-tk
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The package is `python3-tkinter` on Fedora and `tk` on Arch.

The commands in the rest of this README use the Windows paths. On Linux, replace `.venv\Scripts\python` with `.venv/bin/python`.

## Adding your data

Download the transaction exports from each bank's e-banking, wherever you like. Then press **Import files** and select one or more of them. The app suggests the bank of each file from its format; you can change it or type a new bank name before importing.

The transactions are stored in `mymoney.db`, so the app doesn't need the original files afterwards. The app starts empty until you import something.

You can keep importing newer exports. Transactions that appear in more than one file of the same bank are counted only once, and importing the exact same file twice is refused. To undo an import, press **Imports**, select it (the list shows the period each import covers) and press **Delete import**. This removes all of that file's transactions and brings back any it was hiding from another file. Your manual categories are kept, so they apply again if you import the file again.

You can also import from the terminal. The bank is detected from the format unless you pass `--bank`:

```bat
.venv\Scripts\python main.py --import 2026.09.csv statementexport28-10-2026.xlsx
.venv\Scripts\python main.py --import alpha.csv --bank "Alpha Bank"
```

## Running

Double-click `run.bat` on Windows or run `./run.sh` on Linux, or:

```bat
.venv\Scripts\python main.py
```

Use **Year** and **Month** to narrow the period: a whole year, one month of a year, or the same month across all years (e.g. every September). The month list shows only months that have transactions in the selected year. Use **Bank** to pick a single bank or all banks.

### Terminal report

```bat
.venv\Scripts\python main.py --report                    # all banks
.venv\Scripts\python main.py --report --bank piraeus     # one bank (its name or display name)
.venv\Scripts\python main.py --report --year 2026 --month 09   # one month of a year
.venv\Scripts\python main.py --report --year 2026               # one year
```

## Language

The interface is in Greek by default. To switch to English, pick **English** from the language list at the top right of the window. The window switches straight away and keeps your selected month, bank and tab. You can also switch from the command line:

```bat
.venv\Scripts\python main.py --lang en     # or --lang el
```

The choice is saved in `settings.json` and is used the next time the app starts, both in the window and in the terminal report. Amounts are shown as `1.234,56 €` in Greek and `€1,234.56` in English.

Category names are your own data, so they stay as you wrote them in either language.

## Theme

The app opens in the light theme. To switch, press the **☾ Dark** (**☾ Σκοτεινό**) button at the top right of the window, next to the language list; in the dark theme the same button reads **☀ Light** (**☀ Φωτεινό**) and switches back. The charts, tables and, on Windows 10/11, the title bar follow the theme. The window keeps your selected month, bank and tab, and the choice is saved in `settings.json`.

## Categories

Transactions are categorised in this order:

1. A manual category set for that single transaction in the app
2. A manual category set for all transactions with the same description
3. Keywords. The first category with a keyword found in the description wins, and matching ignores case.

To change the category of transactions, open the **Transactions** tab, select one or more (Ctrl/Shift + click, or Ctrl+A for all that are shown) and press **Change category…**. You can apply the choice to those transactions only, or to all transactions with the same description.

To manage the categories themselves, press **Categories**. There you can add, rename, delete and reorder them, mark them as income categories and edit their keywords. Order matters, because categories are checked from the top of the list. Spaces in keywords count too, so `POI ` does not match `POINT`. Deleting a category sends its transactions back to their automatic category. "Λοιπά έσοδα" and "Λοιπά έξοδα" are the fallback categories, so they cannot be renamed or deleted.

Everything is stored in `mymoney.db`. A new database starts with a default set of categories (`mymoney/default_categories.py`). If you have a `manual_categories.json` from an older version, its choices are moved into the database once, the next time the app starts. The file is then no longer used, and you can delete it.

A positive amount counts as income only if its category is marked as an income category. A positive amount in an expense category is treated as a refund and lowers that category's expenses.

## Transfers between banks

When a debit in one bank matches a credit in another bank, the app treats the pair as a transfer. A match needs the same amount, dates no more than 3 days apart, and at least one word in common in the descriptions. In the combined view these pairs are excluded from income and expenses. When you view a single bank they count normally.

## Adding another bank

1. Import its exports and type the bank's name (e.g. `alphabank`) in the import window.
2. Optionally give it a display name in both languages by adding a `bank.<name>` entry (e.g. `bank.alphabank`) to `STRINGS` in `mymoney/i18n.py`.
3. Optionally add its logo as a 20×20 PNG at `mymoney/assets/banks/<name>.png` (e.g. `alphabank.png`). It is shown next to the bank's name in the bank list. Banks without a logo are listed without one.
4. If the export format is new, add a row parser next to `_nbg_row` / `_piraeus_row` in `mymoney/loader.py` and detect it by its column headers in `_xlsx_format` (or add a CSV loader and handle it in `detect_bank`).

## Project structure

```
main.py                  entry point (GUI, --import or --report)
mymoney/loader.py        reading bank exports, de-duplication, inter-bank transfers
mymoney/database.py      the SQLite database of imported transactions and categories
mymoney/categories.py    keyword and manual categorisation
mymoney/default_categories.py  the categories a new database starts with
mymoney/stats.py         statistics
mymoney/gui.py           Tkinter + matplotlib interface
mymoney/i18n.py          Greek/English texts and amount formatting
mymoney/theme.py         light/dark colours and widget styles
mymoney/settings.py      reading and writing settings.json
mymoney/assets/banks/    bank logos for the bank list
mymoney.db               your imported transactions and categories (not committed)
settings.json            your language and theme choice (not committed)
```

## Privacy

`mymoney.db`, `manual_categories.json`, `settings.json` and bank exports kept in `files/` are listed in `.gitignore` and are never committed. The database is not encrypted, so anyone with access to the file can read it.
