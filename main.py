"""MyMoney: στατιστικά εσόδων/εξόδων από τα αρχεία των τραπεζών, που εισάγει ο χρήστης
στη βάση δεδομένων mymoney.db.

Χρήση:
    python main.py            # γραφική εφαρμογή
    python main.py --import ΑΡΧΕΙΟ [ΑΡΧΕΙΟ ...]   # εισαγωγή αρχείων στη βάση
    python main.py --import ΑΡΧΕΙΟ --bank eurobank
    python main.py --report   # αναφορά στο τερματικό (όλες οι τράπεζες)
    python main.py --report --bank eurobank
    python main.py --report --year 2026
    python main.py --report --year 2026 --month 09
    python main.py --lang en  # αγγλικά (αποθηκεύεται στο settings.json)
"""

import argparse
import sys
from pathlib import Path

from mymoney import i18n
from mymoney.i18n import bank_key, bank_label, period_label, t

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "mymoney.db"
OLD_MANUAL_FILE = BASE_DIR / "manual_categories.json"  # μόνο για τη μεταφορά στη βάση
SETTINGS_FILE = BASE_DIR / "settings.json"


def migrate_manual_categories():
    from mymoney.database import migrate_manual_file

    try:
        migrate_manual_file(DB_FILE, OLD_MANUAL_FILE)
    except (OSError, ValueError) as exc:  # χαλασμένο αρχείο: η εφαρμογή ανοίγει και ξαναδοκιμάζει την επόμενη φορά
        print(t("error.migrate_manual", file=OLD_MANUAL_FILE.name, error=exc), file=sys.stderr)


def import_files(paths: list[str], bank: str | None):
    from mymoney.database import import_file, list_imports
    from mymoney.loader import detect_bank

    failed = False
    for name in paths:
        path = Path(name)
        try:
            banks = {record.bank for record in list_imports(DB_FILE)}
            result = import_file(DB_FILE, path, bank_key(bank, banks) if bank else detect_bank(path))
        except Exception as exc:  # ένα χαλασμένο αρχείο δεν σταματά τα υπόλοιπα
            print(f"{path.name}: {exc}", file=sys.stderr)
            failed = True
            continue
        print(t("import.result", file=result.file_name, bank=bank_label(result.bank),
                added=result.added, rows=result.rows))
    if failed:
        sys.exit(1)


def print_report(year: str | None, month: str | None, bank: str | None):
    from mymoney.categories import Categorizer
    from mymoney.database import load_transactions
    from mymoney.loader import split_transfers
    from mymoney.stats import compute, fmt

    txs = load_transactions(DB_FILE)
    if not txs:
        sys.exit(t("report.empty"))
    txs = [tx for tx in txs if tx.in_period(year, month)]
    categorizer = Categorizer.from_db(DB_FILE)
    banks = sorted({tx.bank for tx in txs}, key=bank_label)

    if bank:
        # Δεκτό είτε το όνομα στη βάση είτε το εμφανιζόμενο όνομα.
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

    print(t("report.count", count=len(txs), bank=title, period=period_label(year, month)))
    print(f"{t('report.income'):<10}{fmt(s.income):>15}")
    print(f"{t('report.expenses'):<10}{fmt(s.expenses):>15}")
    print(f"{t('report.net'):<10}{fmt(s.net):>15}")
    print(f"{t('report.balance'):<10}{fmt(s.last_balance):>15}")
    print(t("report.avg_daily", amount=fmt(s.avg_daily_expense)))

    print("\n" + t("report.years"))
    for y in s.years:
        print(f"  {y.year}     " + t("report.year_line", income=f"{fmt(y.income):>13}",
                                     expenses=f"{fmt(y.expenses):>13}", net=f"{fmt(y.net):>13}",
                                     avg=fmt(y.avg_monthly_expense)))

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
    parser.add_argument("--import", dest="import_files", nargs="+", metavar="FILE", help=t("cli.import"))
    parser.add_argument("--report", action="store_true", help=t("cli.report"))
    parser.add_argument("--month", help=t("cli.month"))
    parser.add_argument("--year", help=t("cli.year"))
    parser.add_argument("--bank", help=t("cli.bank"))
    parser.add_argument("--lang", choices=list(i18n.LANGUAGES), help=t("cli.lang"))
    args = parser.parse_args()

    if args.lang:
        i18n.set_language(args.lang)
        i18n.save_settings(SETTINGS_FILE)

    if args.import_files or args.report:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    migrate_manual_categories()

    if args.import_files:
        import_files(args.import_files, args.bank)
        return

    if args.report:
        year, month = args.year, args.month
        if month and "-" in month:  # παλιά μορφή 2026-09
            year, month = month.split("-", 1)
        if month:
            if not month.isdigit() or not 1 <= int(month) <= 12:
                sys.exit(t("report.bad_month", month=args.month))
            month = f"{int(month):02d}"
        print_report(year, month, args.bank)
        return

    try:
        from mymoney import theme
        from mymoney.gui import MyMoneyApp
    except ModuleNotFoundError as exc:
        if exc.name != "tkinter":
            raise
        sys.exit(t("error.no_tkinter"))  # στο Linux είναι συνήθως ξεχωριστό πακέτο

    theme.load_settings(SETTINGS_FILE)

    app = MyMoneyApp(DB_FILE, SETTINGS_FILE)
    app.mainloop()


if __name__ == "__main__":
    main()
