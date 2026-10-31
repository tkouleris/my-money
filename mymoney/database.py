"""Βάση δεδομένων SQLite με τις κινήσεις που εισάγει ο χρήστης από τα αρχεία των τραπεζών.

Κάθε εισαγωγή κρατά όλες τις γραμμές του αρχείου της. Οι κινήσεις που υπάρχουν σε
δύο αρχεία της ίδιας τράπεζας αφαιρούνται κατά την ανάγνωση (merge_files), ώστε η
διαγραφή μιας εισαγωγής να επαναφέρει τις γραμμές που είχε «κρύψει» από άλλο αρχείο.
"""

import hashlib
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from .i18n import t
from .loader import Transaction, load_file, merge_files

# Τα ποσά αποθηκεύονται ως κείμενο, ώστε το Decimal (και άρα το tx_key) να μένει ακριβώς ίδιο.
SCHEMA = """
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL,
    bank TEXT NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    value_date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount TEXT NOT NULL,
    balance TEXT
);
CREATE INDEX IF NOT EXISTS transactions_import ON transactions(import_id);
"""


@dataclass(frozen=True)
class ImportRecord:
    id: int
    file_name: str
    bank: str
    imported_at: datetime
    rows: int


@dataclass(frozen=True)
class ImportResult:
    file_name: str
    bank: str
    rows: int  # γραμμές του αρχείου
    added: int  # νέες κινήσεις, χωρίς όσες υπήρχαν ήδη σε άλλο αρχείο της τράπεζας


@contextmanager
def _connect(path: Path):
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        with conn:  # commit στο τέλος, rollback σε σφάλμα
            yield conn
    finally:
        conn.close()


def load_transactions(db_path: Path) -> list[Transaction]:
    """Κινήσεις όλων των τραπεζών, χωρίς διπλότυπα, χρονολογικά."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT i.id, i.bank, i.file_name, t.date, t.value_date, t.description, t.amount, t.balance "
            "FROM transactions t JOIN imports i ON i.id = t.import_id ORDER BY i.id, t.id"
        ).fetchall()

    banks = defaultdict(lambda: defaultdict(list))  # τράπεζα -> εισαγωγή -> κινήσεις
    for import_id, bank, file_name, tx_date, value_date, description, amount, balance in rows:
        banks[bank][import_id].append(Transaction(
            date=date.fromisoformat(tx_date),
            value_date=date.fromisoformat(value_date),
            description=description,
            amount=Decimal(amount),
            balance=Decimal(balance) if balance is not None else None,
            source=file_name,
            bank=bank,
        ))

    result = []
    for bank in sorted(banks):
        result.extend(merge_files(list(banks[bank].values())))
    result.sort(key=lambda tx: tx.date)
    return result


def import_file(db_path: Path, path: Path, bank: str) -> ImportResult:
    """Εισάγει ένα αρχείο στη βάση. Σε σφάλμα ή αν το αρχείο έχει ήδη εισαχθεί,
    πετάει εξαίρεση και η βάση μένει ως είχε."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with _connect(db_path) as conn:
        existing = conn.execute("SELECT bank FROM imports WHERE sha256 = ?", (digest,)).fetchone()
    if existing:
        raise ValueError(t("error.already_imported", bank=existing[0]))
    txs = load_file(path, bank)
    if not txs:
        raise ValueError(t("error.no_transactions"))

    before = sum(tx.bank == bank for tx in load_transactions(db_path))
    with _connect(db_path) as conn:
        import_id = conn.execute(
            "INSERT INTO imports (file_name, bank, sha256, imported_at) VALUES (?, ?, ?, ?)",
            (path.name, bank, digest, datetime.now().isoformat(" ", "seconds")),
        ).lastrowid
        conn.executemany(
            "INSERT INTO transactions (import_id, date, value_date, description, amount, balance) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(import_id, tx.date.isoformat(), tx.value_date.isoformat(), tx.description, str(tx.amount),
              str(tx.balance) if tx.balance is not None else None) for tx in txs],
        )
    after = sum(tx.bank == bank for tx in load_transactions(db_path))
    return ImportResult(path.name, bank, len(txs), after - before)


def list_imports(db_path: Path) -> list[ImportRecord]:
    """Οι εισαγωγές που έχουν γίνει, οι νεότερες πρώτες."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT i.id, i.file_name, i.bank, i.imported_at, COUNT(t.id) "
            "FROM imports i LEFT JOIN transactions t ON t.import_id = i.id "
            "GROUP BY i.id ORDER BY i.id DESC"
        ).fetchall()
    return [ImportRecord(id_, name, bank, datetime.fromisoformat(at), count)
            for id_, name, bank, at, count in rows]


def delete_import(db_path: Path, import_id: int):
    """Διαγράφει μία εισαγωγή μαζί με τις γραμμές της."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM imports WHERE id = ?", (import_id,))
