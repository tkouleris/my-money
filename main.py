"""MyMoney: στατιστικά εσόδων/εξόδων από τα αρχεία των τραπεζών στον φάκελο files
(ένας υποφάκελος ανά τράπεζα, π.χ. files/eurobank, files/nationalbank).

Χρήση:
    python main.py            # γραφική εφαρμογή
    python main.py --report   # αναφορά στο τερματικό (όλες οι τράπεζες)
    python main.py --report --bank eurobank
    python main.py --lang en  # αγγλικά (αποθηκεύεται στο settings.json)
"""

import argparse
import sys
from pathlib import Path

from mymoney import i18n
from mymoney.i18n import bank_label, t

BASE_DIR = Path(__file__).resolve().parent
FILES_DIR = BASE_DIR / "files"
CATEGORIES_FILE = BASE_DIR / "categories.json"
MANUAL_FILE = BASE_DIR / "manual_categories.json"
SETTINGS_FILE = BASE_DIR / "settings.json"


def print_report(month: str | None, bank: str | None):
    from mymoney.categories import Categorizer
    from mymoney.loader import load_banks, split_transfers
    from mymoney.stats import compute, fmt

    txs = load_banks(FILES_DIR)
    if month:
        txs = [tx for tx in txs if tx.month == month]
    categorizer = Categorizer.from_file(CATEGORIES_FILE, MANUAL_FILE)
    banks = sorted({tx.bank for tx in txs}, key=bank_label)

    if bank:
        # Δεκτό είτε το όνομα του φακέλου είτε το εμφανιζόμενο όνομα.
        matches = [b for b in banks if bank.casefold() in (b.casefold(), bank_label(b).casefold())]
        if not matches:
            sys.exit(t("report.unknown_bank", bank=bank, banks=", ".join(banks)))
        txs = [tx for tx in txs if tx.bank == matches[0]]
        title = bank_label(matches[0])
    else:
        title = t("all_banks")
        print(t("report.by_bank"))
        for b in banks:
            bs = compute([tx for tx in txs if tx.bank == b], categorizer)
            print(f"  {bank_label(b):<24} " + t("report.bank_line", income=f"{fmt(bs.income):>13}",
                                                  expenses=f"{fmt(bs.expenses):>13}",
                                                  balance=f"{fmt(bs.last_balance):>13}"))
        txs, transfers = split_transfers(txs)
        if transfers:
            moved = sum(tx.amount for tx in transfers if tx.amount > 0)
            print("  " + t("report.transfers", count=len(transfers) // 2, amount=fmt(moved)))
        print()
    s = compute(txs, categorizer)

    print(t("report.count", count=len(txs), bank=title, period=month or t("all_months")))
    print(f"{t('report.income'):<10}{fmt(s.income):>15}")
    print(f"{t('report.expenses'):<10}{fmt(s.expenses):>15}")
    print(f"{t('report.net'):<10}{fmt(s.net):>15}")
    print(f"{t('report.balance'):<10}{fmt(s.last_balance):>15}")
    print(t("report.avg_daily", amount=fmt(s.avg_daily_expense)))

    print("\n" + t("report.months"))
    for m in s.months:
        print(f"  {m.month}  " + t("report.month_line", income=f"{fmt(m.income):>13}",
                                   expenses=f"{fmt(m.expenses):>13}", net=f"{fmt(m.net):>13}"))

    print("\n" + t("report.categories"))
    for c in s.expense_categories:
        pct = c.total / s.expenses * 100
        print(f"  {c.name:<28} {fmt(c.total):>13}  {pct:5.1f}%  ({c.count})")

    print("\n" + t("report.top"))
    for m in s.top_merchants[:10]:
        print(f"  {m.name:<34} {fmt(m.total):>13}  ({m.count})")


def main():
    i18n.load_settings(SETTINGS_FILE)

    parser = argparse.ArgumentParser(description=t("cli.description"))
    parser.add_argument("--report", action="store_true", help=t("cli.report"))
    parser.add_argument("--month", help=t("cli.month"))
    parser.add_argument("--bank", help=t("cli.bank"))
    parser.add_argument("--lang", choices=list(i18n.LANGUAGES), help=t("cli.lang"))
    args = parser.parse_args()

    if args.lang:
        i18n.set_language(args.lang)
        i18n.save_settings(SETTINGS_FILE)

    if args.report:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        print_report(args.month, args.bank)
        return

    from mymoney.gui import MyMoneyApp

    app = MyMoneyApp(FILES_DIR, CATEGORIES_FILE, MANUAL_FILE, SETTINGS_FILE)
    app.mainloop()


if __name__ == "__main__":
    main()
