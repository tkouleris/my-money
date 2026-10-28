# MyMoney

A small desktop app that reads the transaction exports of your Greek bank accounts and shows income and expense statistics. You can view each bank on its own or all banks combined.

Everything runs locally. Your bank files never leave your computer.

## Features

- Income, expenses, net result, latest balance and average daily spending
- Yearly and monthly income vs. expenses (chart + table), with average monthly spending per year
- Per-bank comparison, with a combined total
- Expenses by category, daily expenses, top merchants
- Searchable transaction list with a bank and category filter
- Automatic categorisation by keywords, plus manual categories you set from the app
- Transfers between your own banks are detected and left out of the combined total, so they are not counted twice
- Overlapping exports of the same bank are de-duplicated
- A plain-text report for the terminal
- Greek (default) and English interface

## Supported banks

| Folder               | Bank           | Export format                                               | Balance |
|----------------------|----------------|-------------------------------------------------------------|---------|
| `files/eurobank`     | Eurobank       | `.csv` (`;`-separated, Greek number format)                 | yes     |
| `files/nationalbank` | National Bank  | `.xlsx` (`statementexport…`)                                 | yes     |
| `files/piraeus`      | Piraeus Bank   | `.xlsx` (Λίστα Ενοποιημένων Συναλλαγών)                     | no      |

The app tells the two `.xlsx` formats apart by their column headers, so the file names don't matter.

## Requirements

- Python 3.10 or newer
- Windows for `run.bat`. The app itself uses Tkinter, so it also runs on other platforms with `python main.py`.

## Setup

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Adding your data

Download the transaction exports from each bank's e-banking and put them in the matching folder:

```
files/
├── eurobank/        2026.01_2026.08.csv, 2026.09.csv, ...
├── nationalbank/    statementexport28-10-2026.xlsx
└── piraeus/         Λίστα Ενοποιημένων Συναλλαγών_20261028.xlsx
```

You can keep adding newer exports to a folder. Transactions that appear in more than one file of the same bank are counted only once.

## Running

Double-click `run.bat`, or:

```bat
.venv\Scripts\python main.py
```

Use **Year** and **Month** to narrow the period: a whole year, one month of a year, or the same month across all years (e.g. every September). The month list shows only months that have transactions in the selected year. Use **Bank** to pick a single bank or all banks. After adding new files, press **Reload files** to reload them.

### Terminal report

```bat
.venv\Scripts\python main.py --report                    # all banks
.venv\Scripts\python main.py --report --bank piraeus     # one bank (folder name or display name)
.venv\Scripts\python main.py --report --year 2026 --month 09   # one month of a year
.venv\Scripts\python main.py --report --year 2026               # one year
```

## Language

The interface is in Greek by default. To switch to English, pick **English** from the language list at the top right of the window. The window switches straight away and keeps your selected month, bank and tab. You can also switch from the command line:

```bat
.venv\Scripts\python main.py --lang en     # or --lang el
```

The choice is saved in `settings.json` and is used the next time the app starts, both in the window and in the terminal report. Amounts are shown as `1.234,56 €` in Greek and `€1,234.56` in English.

Category names come from `categories.json` and your manual choices, so they stay as you wrote them in either language.

## Categories

Transactions are categorised in this order:

1. A manual category set for that single transaction in the app
2. A manual category set for all transactions with the same description
3. Keywords in `categories.json`. The first category with a keyword found in the description wins, and matching ignores case.

Manual choices are saved to `manual_categories.json`. To edit the keyword rules, use the **Κατηγορίες** button or open `categories.json` directly, then reload.

A positive amount counts as income only if its category is listed in `income_categories` (or is "Λοιπά έσοδα"). A positive amount in an expense category is treated as a refund and lowers that category's expenses.

## Transfers between banks

When a debit in one bank matches a credit in another bank, the app treats the pair as a transfer. A match needs the same amount, dates no more than 3 days apart, and at least one word in common in the descriptions. In the combined view these pairs are excluded from income and expenses. When you view a single bank they count normally.

## Adding another bank

1. Create a folder under `files/` (e.g. `files/alphabank`) and put the exports there.
2. Optionally give it a display name in both languages by adding a `bank.<folder>` entry (e.g. `bank.alphabank`) to `STRINGS` in `mymoney/i18n.py`.
3. If the export format is new, add a row parser next to `_nbg_row` / `_piraeus_row` in `mymoney/loader.py` and detect it by its column headers in `load_xlsx` (or add a CSV loader).

## Project structure

```
main.py                  entry point (GUI or --report)
mymoney/loader.py        reading bank exports, de-duplication, inter-bank transfers
mymoney/categories.py    keyword and manual categorisation
mymoney/stats.py         statistics
mymoney/gui.py           Tkinter + matplotlib interface
mymoney/i18n.py          Greek/English texts and amount formatting
categories.json          category keyword rules
manual_categories.json   your manual category choices (not committed)
settings.json            your language choice (not committed)
```

## Privacy

Bank exports in `files/`, `manual_categories.json` and `settings.json` are listed in `.gitignore` and are never committed. Only the folder structure is kept, using `.gitkeep` files.
