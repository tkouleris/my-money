"""Φόρτωση κινήσεων από τα αρχεία των τραπεζών.

Κάθε υποφάκελος του files είναι μία τράπεζα (π.χ. files/eurobank,
files/nationalbank, files/piraeus). Υποστηρίζονται:
- .csv  : εξαγωγή Eurobank (ημ/νία;ημ/νία αξίας;περιγραφή;ποσό;υπόλοιπο)
- .xlsx : εξαγωγή Εθνικής Τράπεζας (statementexport) ή Πειραιώς (Λίστα
          Ενοποιημένων Συναλλαγών)· η μορφή αναγνωρίζεται από τις στήλες.
"""

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .i18n import t


@dataclass(frozen=True)
class Transaction:
    date: date
    value_date: date
    description: str
    amount: Decimal
    balance: Decimal | None
    source: str
    bank: str = ""  # όνομα φακέλου της τράπεζας, π.χ. «eurobank»

    @property
    def is_income(self) -> bool:
        return self.amount > 0

    @property
    def month(self) -> str:
        return self.date.strftime("%Y-%m")

    @property
    def year(self) -> str:
        return self.date.strftime("%Y")

    def in_period(self, year: str | None = None, month: str | None = None) -> bool:
        """year π.χ. «2026», month π.χ. «09»· None σημαίνει όλα."""
        return ((year is None or self.date.strftime("%Y") == year)
                and (month is None or self.date.strftime("%m") == month))


def parse_amount(text: str) -> Decimal:
    """Μετατρέπει ελληνική μορφή αριθμού (1.786,63) σε Decimal."""
    cleaned = text.strip().replace(".", "").replace(",", ".")
    return Decimal(cleaned)


def parse_date(text: str) -> date:
    return datetime.strptime(text.strip(), "%d/%m/%Y").date()


SUPPORTED_SUFFIXES = (".csv", ".xlsx")


def load_file(path: Path, bank: str = "") -> list[Transaction]:
    if path.suffix.casefold() == ".xlsx":
        return load_xlsx(path, bank)
    return load_csv(path, bank)


def load_csv(path: Path, bank: str = "") -> list[Transaction]:
    transactions = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)  # επικεφαλίδα
        for row in reader:
            if len(row) < 4:
                continue
            try:
                tx_date = parse_date(row[0])
                value_date = parse_date(row[1]) if row[1].strip() else tx_date
                amount = parse_amount(row[3])
            except (ValueError, InvalidOperation):
                # Κενές γραμμές και υποσέλιδα (αριθμός λογαριασμού κλπ.)
                continue
            balance = None
            if len(row) > 4 and row[4].strip():
                try:
                    balance = parse_amount(row[4])
                except InvalidOperation:
                    pass
            transactions.append(
                Transaction(
                    date=tx_date,
                    value_date=value_date,
                    description=" ".join(row[2].split()),
                    amount=amount,
                    balance=balance,
                    source=path.name,
                    bank=bank,
                )
            )
    # Η τράπεζα δίνει τις νεότερες κινήσεις πρώτες· τις θέλουμε χρονολογικά.
    transactions.reverse()
    return transactions


def _to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return parse_date(str(value))


def _to_decimal(value) -> Decimal:
    if isinstance(value, (int, float)):
        return Decimal(str(round(value, 2)))
    return parse_amount(str(value))


NBG_COLUMNS = ("Ημερομηνία", "Περιγραφή", "Ποσό συναλλαγής")
PIRAEUS_COLUMNS = ("Περιγραφή Συναλλαγής (είδος)", "Ημερομηνία Καταχώρησης", "Ποσό")

# Στην Πειραιώς το είδος της κίνησης είναι κολλημένο στο τέλος της περιγραφής,
# π.χ. «SKROUTZ NEA IONIA(ΑΓΟΡΑ ΜΕ ΚΑΡΤΑ)». Για αγορές και επιστροφές με κάρτα
# το αφαιρούμε, ώστε αγορά και επιστροφή στον ίδιο έμπορο να έχουν ίδια περιγραφή.
PIRAEUS_CARD_SUFFIX = re.compile(r"\((ΑΓΟΡΑ ΜΕ ΚΑΡΤΑ|ΑΝΤΙΛ/ΜΟΣ ΑΓΟΡΑΣ ΜΕ ΚΑΡΤΑ)\)\s*$")


def load_xlsx(path: Path, bank: str = "") -> list[Transaction]:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb["data"] if "data" in wb.sheetnames else wb.worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    # Η επικεφαλίδα δεν είναι πάντα στην πρώτη γραμμή (η Πειραιώς έχει τίτλο από πάνω).
    for i, row in enumerate(rows[:20]):
        header = [str(h).strip() if h is not None else "" for h in row]
        col = {name: j for j, name in enumerate(header) if name}
        if all(name in col for name in PIRAEUS_COLUMNS):
            parse = _piraeus_row
            break
        if all(name in col for name in NBG_COLUMNS):
            parse = _nbg_row
            break
    else:
        raise ValueError(t("error.unknown_xlsx", file=path.name))

    transactions = []
    for row in rows[i + 1:]:

        def cell(name):
            j = col.get(name)
            return row[j] if j is not None and j < len(row) else None

        try:
            tx = parse(cell)
        except (ValueError, TypeError, InvalidOperation):
            # Κενές γραμμές και υποσέλιδα («Ημερομηνία Ενημέρωσης» κλπ.)
            continue
        transactions.append(Transaction(**tx, source=path.name, bank=bank))
    # Κι εδώ οι νεότερες κινήσεις είναι πρώτες.
    transactions.reverse()
    return transactions


def _nbg_row(cell) -> dict:
    """Γραμμή εξαγωγής Εθνικής Τράπεζας (φύλλο «data»)."""
    tx_date = _to_date(cell("Ημερομηνία"))
    valeur = cell("Valeur")
    signed = cell("Ποσό εντολής")
    if signed is not None:
        amount = _to_decimal(signed)
    else:
        amount = abs(_to_decimal(cell("Ποσό συναλλαγής")))
        if str(cell("Χρέωση / Πίστωση") or "").strip() == "Χ":
            amount = -amount
    balance = None
    if cell("Λογιστικό Υπόλοιπο") is not None:
        try:
            balance = _to_decimal(cell("Λογιστικό Υπόλοιπο"))
        except (ValueError, InvalidOperation):
            pass
    description = cell("Περιγραφή") or cell("Ονοματεπώνυμο αντισυμβαλλόμενου") or ""
    return dict(
        date=tx_date,
        value_date=_to_date(valeur) if valeur else tx_date,
        description=" ".join(str(description).split()),
        amount=amount,
        balance=balance,
    )


def _piraeus_row(cell) -> dict:
    """Γραμμή «Λίστας Ενοποιημένων Συναλλαγών» Πειραιώς (χωρίς υπόλοιπο)."""
    tx_date = _to_date(cell("Ημερομηνία Καταχώρησης"))
    amount = _to_decimal(cell("Ποσό"))
    description = PIRAEUS_CARD_SUFFIX.sub("", str(cell("Περιγραφή Συναλλαγής (είδος)") or ""))
    return dict(
        date=tx_date,
        value_date=tx_date,
        description=" ".join(description.split()),
        amount=amount,
        balance=None,
    )


def _match_key(tx: Transaction) -> tuple:
    """Κλειδί για εντοπισμό της ίδιας κίνησης σε διαφορετικά αρχεία.

    Οι εξαγωγές διαφέρουν στη μορφή: π.χ. η εξαγωγή κάρτας γράφει «eΦooΔ» με
    ημερομηνία συναλλαγής 30/08 και αξίας 01/09, ενώ η εξαγωγή λογαριασμού
    γράφει «eΦooΔ Herak GR» με ημερομηνία 01/09. Κοινά μένουν η ημερομηνία
    αξίας, το ποσό και η αρχή της περιγραφής."""
    prefix = "".join(ch for ch in tx.description.casefold() if ch.isalnum())[:5]
    return (tx.value_date, tx.amount, prefix)


def load_folder(folder: Path, bank: str = "") -> list[Transaction]:
    """Διαβάζει όλα τα αρχεία του φακέλου και αφαιρεί κινήσεις που υπάρχουν ήδη
    σε άλλο αρχείο (όταν δύο εξαγωγές καλύπτουν τις ίδιες ημερομηνίες).
    Ίδιες κινήσεις μέσα στο ίδιο αρχείο (π.χ. δύο καφέδες την ίδια μέρα)
    κρατιούνται όλες."""
    files = [load_file(path, bank) for path in data_files(folder)]
    # Προτιμάμε τα αρχεία με υπόλοιπο (εξαγωγή λογαριασμού) όταν υπάρχει επικάλυψη.
    files.sort(key=lambda txs: not any(t.balance is not None for t in txs))

    available = Counter()  # κινήσεις προηγούμενων αρχείων που δεν έχουν «αντιστοιχιστεί»
    result = []
    for txs in files:
        keys = [_match_key(tx) for tx in txs]
        for tx, key in zip(txs, keys):
            if available[key] > 0:
                available[key] -= 1
                continue
            result.append(tx)
        available.update(keys)
    result.sort(key=lambda t: t.date)
    return result


def data_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.glob("*")
                  if p.suffix.casefold() in SUPPORTED_SUFFIXES and not p.name.startswith("~$"))


def bank_folders(files_dir: Path) -> list[Path]:
    return sorted(p for p in files_dir.iterdir() if p.is_dir()) if files_dir.exists() else []


def load_banks(files_dir: Path) -> list[Transaction]:
    """Κινήσεις όλων των τραπεζών (ένας υποφάκελος ανά τράπεζα), χρονολογικά."""
    result = []
    for folder in bank_folders(files_dir):
        result.extend(load_folder(folder, folder.name))
    result.sort(key=lambda t: t.date)
    return result


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^\w]+", text.casefold()) if len(w) >= 3}


def split_transfers(transactions: list[Transaction], max_days: int = 3):
    """Βρίσκει μεταφορές μεταξύ των τραπεζών: χρέωση σε μία τράπεζα και πίστωση
    ίδιου ποσού σε άλλη, με διαφορά έως max_days ημέρες και κοινή λέξη στην
    περιγραφή (π.χ. «POO RENT POWER INTERNET» / «RENT POWER INTERNET»).

    Επιστρέφει (υπόλοιπες κινήσεις, μεταφορές). Στο σύνολο όλων των τραπεζών οι
    μεταφορές δεν είναι ούτε έσοδο ούτε έξοδο, απλώς μετακίνηση χρημάτων."""
    debits = defaultdict(list)  # ποσό -> δείκτες χρεώσεων
    for i, tx in enumerate(transactions):
        if tx.amount < 0:
            debits[-tx.amount].append(i)

    matched = set()
    for i, tx in enumerate(transactions):
        if tx.amount <= 0:
            continue
        words = _words(tx.description)
        candidates = [
            j for j in debits.get(tx.amount, [])
            if j not in matched
            and transactions[j].bank != tx.bank
            and abs((transactions[j].date - tx.date).days) <= max_days
            and words & _words(transactions[j].description)
        ]
        if candidates:
            j = min(candidates, key=lambda j: abs((transactions[j].date - tx.date).days))
            matched.update((i, j))

    kept = [t for i, t in enumerate(transactions) if i not in matched]
    transfers = [t for i, t in enumerate(transactions) if i in matched]
    return kept, transfers
