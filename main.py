"""MyMoney: στατιστικά εσόδων/εξόδων από τα αρχεία των τραπεζών στον φάκελο files
(ένας υποφάκελος ανά τράπεζα, π.χ. files/eurobank, files/nationalbank).

Χρήση:
    python main.py            # γραφική εφαρμογή
    python main.py --report   # αναφορά στο τερματικό (όλες οι τράπεζες)
    python main.py --report --bank eurobank
"""

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FILES_DIR = BASE_DIR / "files"
CATEGORIES_FILE = BASE_DIR / "categories.json"
MANUAL_FILE = BASE_DIR / "manual_categories.json"


def print_report(month: str | None, bank: str | None):
    from mymoney.categories import Categorizer
    from mymoney.loader import bank_name, load_banks, split_transfers
    from mymoney.stats import compute, fmt

    txs = load_banks(FILES_DIR)
    if month:
        txs = [t for t in txs if t.month == month]
    categorizer = Categorizer.from_file(CATEGORIES_FILE, MANUAL_FILE)
    banks = sorted({t.bank for t in txs})

    if bank:
        wanted = bank_name(Path(bank))
        matches = [b for b in banks if b.casefold() in (bank.casefold(), wanted.casefold())]
        if not matches:
            sys.exit(f"Άγνωστη τράπεζα «{bank}». Διαθέσιμες: {', '.join(banks)}")
        txs = [t for t in txs if t.bank == matches[0]]
        title = matches[0]
    else:
        title = "όλες οι τράπεζες"
        print("Ανά τράπεζα")
        for b in banks:
            bs = compute([t for t in txs if t.bank == b], categorizer)
            print(f"  {b:<18} έσοδα {fmt(bs.income):>13}  έξοδα {fmt(bs.expenses):>13}  "
                  f"υπόλοιπο {fmt(bs.last_balance):>13}")
        txs, transfers = split_transfers(txs)
        if transfers:
            moved = sum(t.amount for t in transfers if t.amount > 0)
            print(f"  ({len(transfers) // 2} μεταφορές μεταξύ τραπεζών, {fmt(moved)}, "
                  "εκτός συνόλου)")
        print()
    s = compute(txs, categorizer)

    print(f"Κινήσεις: {len(txs)}  ({title}, {month or 'όλοι οι μήνες'})")
    print(f"Έσοδα:    {fmt(s.income):>15}")
    print(f"Έξοδα:    {fmt(s.expenses):>15}")
    print(f"Καθαρό:   {fmt(s.net):>15}")
    print(f"Υπόλοιπο: {fmt(s.last_balance):>15}")
    print(f"Μέσο έξοδο/ημέρα: {fmt(s.avg_daily_expense)}")

    print("\nΑνά μήνα")
    for m in s.months:
        print(f"  {m.month}  έσοδα {fmt(m.income):>13}  έξοδα {fmt(m.expenses):>13}  καθαρό {fmt(m.net):>13}")

    print("\nΈξοδα ανά κατηγορία")
    for c in s.expense_categories:
        pct = c.total / s.expenses * 100
        print(f"  {c.name:<28} {fmt(c.total):>13}  {pct:5.1f}%  ({c.count})")

    print("\nTop 10 έμποροι")
    for m in s.top_merchants[:10]:
        print(f"  {m.name:<34} {fmt(m.total):>13}  ({m.count})")


def main():
    parser = argparse.ArgumentParser(description="Στατιστικά εσόδων/εξόδων")
    parser.add_argument("--report", action="store_true", help="εκτύπωση αναφοράς αντί για παράθυρο")
    parser.add_argument("--month", help="φίλτρο μήνα για την αναφορά, π.χ. 2026-09")
    parser.add_argument("--bank", help="μόνο μία τράπεζα, π.χ. eurobank ή nationalbank")
    args = parser.parse_args()

    if args.report:
        sys.stdout.reconfigure(encoding="utf-8")
        print_report(args.month, args.bank)
        return

    from mymoney.gui import MyMoneyApp

    app = MyMoneyApp(FILES_DIR, CATEGORIES_FILE, MANUAL_FILE)
    app.mainloop()


if __name__ == "__main__":
    main()
