# MyMoney

A small desktop app that reads the transaction exports of your Greek bank accounts and shows income and expense statistics. You can view each bank on its own or all banks combined.

Everything runs locally. Your bank files never leave your computer.

## Features

- Income, expenses, net result, latest balance and average daily spending
- Monthly income vs. expenses (chart + table)
- Per-bank comparison, with a combined total
- Expenses by category, daily expenses, top merchants
- Searchable transaction list with a bank and category filter
- Automatic categorisation by keywords, plus manual categories you set from the app
- Transfers between your own banks are detected and left out of the combined total, so they are not counted twice
- Overlapping exports of the same bank are de-duplicated
- A plain-text report for the terminal

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

Use **Περίοδος** to pick a month and **Τράπεζα** to pick a single bank or all banks. After adding new files, press **Επαναφόρτωση αρχείων** to reload them.

### Terminal report

```bat
.venv\Scripts\python main.py --report                    # all banks
.venv\Scripts\python main.py --report --bank piraeus     # one bank (folder name or display name)
.venv\Scripts\python main.py --report --month 2026-09    # one month
```

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
2. Optionally give it a display name in `BANK_NAMES` in `mymoney/loader.py`.
3. If the export format is new, add a row parser next to `_nbg_row` / `_piraeus_row` in `mymoney/loader.py` and detect it by its column headers in `load_xlsx` (or add a CSV loader).

## Project structure

```
main.py                  entry point (GUI or --report)
mymoney/loader.py        reading bank exports, de-duplication, inter-bank transfers
mymoney/categories.py    keyword and manual categorisation
mymoney/stats.py         statistics
mymoney/gui.py           Tkinter + matplotlib interface
categories.json          category keyword rules
manual_categories.json   your manual category choices (not committed)
```

## Privacy

Bank exports in `files/` and `manual_categories.json` are listed in `.gitignore` and are never committed. Only the folder structure is kept, using `.gitkeep` files.
