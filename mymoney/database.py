"""Βάση δεδομένων SQLite με τις κινήσεις που εισάγει ο χρήστης από τα αρχεία των τραπεζών
και τις κατηγορίες τους.

Κάθε εισαγωγή κρατά όλες τις γραμμές του αρχείου της. Οι κινήσεις που υπάρχουν σε
δύο αρχεία της ίδιας τράπεζας αφαιρούνται κατά την ανάγνωση (merge_files), ώστε η
διαγραφή μιας εισαγωγής να επαναφέρει τις γραμμές που είχε «κρύψει» από άλλο αρχείο.

Ο χρήστης μπορεί να προσθέσει δικές του κινήσεις (manual_entries) και να διαγράψει
οποιαδήποτε κίνηση. Οι κινήσεις των αρχείων δεν σβήνονται από τη βάση: γράφονται στο
deleted_transactions και κρύβονται κατά την ανάγνωση, ώστε να μην ξαναεμφανιστούν με
νέα εισαγωγή του ίδιου αρχείου και να μπορούν να επανέλθουν.

Οι χειροκίνητες κατηγορίες και οι περιγραφές που αλλάζει ο χρήστης κρατιούνται με κλειδί το tx_key και όχι ως στήλη των γραμμών,
ώστε να ισχύουν για τη γραμμή οποιουδήποτε αρχείου και να μη χάνονται με τη διαγραφή
μιας εισαγωγής.
"""

import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from .default_categories import DEFAULT_CATEGORIES, SYSTEM_CATEGORIES
from .i18n import t
from .loader import Transaction, load_file, merge_files

# PRAGMA user_version: 1 = έχουν μπει οι αρχικές κατηγορίες, 2 = έχει μεταφερθεί και το manual_categories.json
VERSION_SEEDED = 1
VERSION_MANUAL_MIGRATED = 2

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
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    is_income INTEGER NOT NULL DEFAULT 0,
    position INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS category_keywords (
    id INTEGER PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    position INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS category_keywords_category ON category_keywords(category_id);
CREATE TABLE IF NOT EXISTS manual_transactions (
    tx_key TEXT PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS manual_descriptions (
    description TEXT PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS custom_descriptions (
    tx_key TEXT PRIMARY KEY,
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS manual_entries (
    id INTEGER PRIMARY KEY,
    bank TEXT NOT NULL,
    date TEXT NOT NULL,
    value_date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount TEXT NOT NULL,
    created_at TEXT NOT NULL
);
-- Μία γραμμή για κάθε διαγραμμένη εμφάνιση: δύο ίδιες κινήσεις (π.χ. δύο καφέδες την
-- ίδια μέρα) έχουν το ίδιο tx_key, οπότε η διαγραφή της μίας κρύβει μόνο μία.
CREATE TABLE IF NOT EXISTS deleted_transactions (
    id INTEGER PRIMARY KEY,
    bank TEXT NOT NULL,
    tx_key TEXT NOT NULL,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount TEXT NOT NULL,
    deleted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS deleted_transactions_key ON deleted_transactions(bank, tx_key);
"""


@dataclass(frozen=True)
class ImportRecord:
    id: int
    file_name: str
    bank: str
    imported_at: datetime
    rows: int
    first_date: date | None  # η περίοδος που καλύπτουν οι γραμμές της εισαγωγής
    last_date: date | None


@dataclass(frozen=True)
class ImportResult:
    file_name: str
    bank: str
    rows: int  # γραμμές του αρχείου
    added: int  # νέες κινήσεις, χωρίς όσες υπήρχαν ήδη σε άλλο αρχείο της τράπεζας


@dataclass(frozen=True)
class DeletedRecord:
    id: int
    bank: str
    date: date
    description: str
    amount: Decimal
    deleted_at: datetime


@dataclass(frozen=True)
class CategoryRecord:
    id: int
    name: str
    is_income: bool
    keywords: list[str]

    @property
    def is_system(self) -> bool:
        return self.name in SYSTEM_CATEGORIES


@contextmanager
def _connect(path: Path):
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        _seed_categories(conn)
        with conn:  # commit στο τέλος, rollback σε σφάλμα
            yield conn
    finally:
        conn.close()


def _version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _seed_categories(conn: sqlite3.Connection):
    """Οι αρχικές κατηγορίες μπαίνουν μία φορά, ώστε όσες σβήσει ο χρήστης να μην ξαναγυρίζουν."""
    if _version(conn) >= VERSION_SEEDED:
        return
    with conn:
        for position, (name, is_income, keywords) in enumerate(DEFAULT_CATEGORIES):
            category_id = conn.execute(
                "INSERT INTO categories (name, is_income, position) VALUES (?, ?, ?)",
                (name, is_income, position),
            ).lastrowid
            _insert_keywords(conn, category_id, keywords)
        conn.execute(f"PRAGMA user_version = {VERSION_SEEDED}")


def _insert_keywords(conn: sqlite3.Connection, category_id: int, keywords: list[str]):
    conn.executemany(
        "INSERT INTO category_keywords (category_id, keyword, position) VALUES (?, ?, ?)",
        [(category_id, keyword, position) for position, keyword in enumerate(keywords)],
    )


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

    with _connect(db_path) as conn:
        entries = conn.execute(
            "SELECT id, bank, date, value_date, description, amount FROM manual_entries ORDER BY id"
        ).fetchall()
        hidden = Counter(conn.execute("SELECT bank, tx_key FROM deleted_transactions").fetchall())

    result = []
    for bank in sorted(banks):
        for tx in merge_files(list(banks[bank].values())):
            key = (tx.bank, tx_key(tx))
            if hidden[key]:
                hidden[key] -= 1
                continue
            result.append(tx)
    # οι κινήσεις του χρήστη δεν περνούν από το merge_files: δεν είναι διπλότυπα κάποιου αρχείου
    result.extend(Transaction(
        date=date.fromisoformat(tx_date),
        value_date=date.fromisoformat(value_date),
        description=description,
        amount=Decimal(amount),
        balance=None,
        source="",
        bank=bank,
        entry_id=entry_id,
    ) for entry_id, bank, tx_date, value_date, description, amount in entries)
    result.sort(key=lambda tx: tx.date)
    return result


def tx_key(tx: Transaction) -> str:
    """Σταθερό αναγνωριστικό κίνησης για αποθήκευση των επιλογών του χρήστη."""
    return f"{tx.date:%Y-%m-%d}|{tx.value_date:%Y-%m-%d}|{tx.description}|{tx.amount}"


# ---------- κινήσεις του χρήστη και διαγραφές ----------

def add_entry(db_path: Path, bank: str, tx_date: date, description: str, amount: Decimal) -> Transaction:
    """Προσθέτει κίνηση που δεν υπάρχει σε αρχείο (π.χ. πληρωμή με μετρητά)."""
    if not bank:
        raise ValueError(t("entry.bank_empty"))
    if not description:
        raise ValueError(t("entry.description_empty"))
    if not amount:
        raise ValueError(t("entry.amount_zero"))
    with _connect(db_path) as conn:
        entry_id = conn.execute(
            "INSERT INTO manual_entries (bank, date, value_date, description, amount, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (bank, tx_date.isoformat(), tx_date.isoformat(), description, str(amount),
             datetime.now().isoformat(" ", "seconds")),
        ).lastrowid
    return Transaction(tx_date, tx_date, description, amount, None, "", bank, entry_id)


def delete_transactions(db_path: Path, txs: list[Transaction]):
    """Οι κινήσεις του χρήστη σβήνονται οριστικά· των αρχείων κρύβονται, ώστε να
    μπορούν να επανέλθουν με restore_deleted."""
    now = datetime.now().isoformat(" ", "seconds")
    with _connect(db_path) as conn:
        conn.executemany("DELETE FROM manual_entries WHERE id = ?",
                         [(tx.entry_id,) for tx in txs if tx.is_manual_entry])
        conn.executemany(
            "INSERT INTO deleted_transactions (bank, tx_key, date, description, amount, deleted_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(tx.bank, tx_key(tx), tx.date.isoformat(), tx.description, str(tx.amount), now)
             for tx in txs if not tx.is_manual_entry],
        )


def list_deleted(db_path: Path) -> list[DeletedRecord]:
    """Οι κινήσεις αρχείων που έχει διαγράψει ο χρήστης, οι πιο πρόσφατες διαγραφές πρώτες."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, bank, date, description, amount, deleted_at FROM deleted_transactions "
            "ORDER BY deleted_at DESC, id DESC"
        ).fetchall()
    return [DeletedRecord(id_, bank, date.fromisoformat(tx_date), description, Decimal(amount),
                          datetime.fromisoformat(at))
            for id_, bank, tx_date, description, amount, at in rows]


def restore_deleted(db_path: Path, ids: list[int]):
    with _connect(db_path) as conn:
        conn.executemany("DELETE FROM deleted_transactions WHERE id = ?", [(id_,) for id_ in ids])


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
            "SELECT i.id, i.file_name, i.bank, i.imported_at, COUNT(t.id), MIN(t.date), MAX(t.date) "
            "FROM imports i LEFT JOIN transactions t ON t.import_id = i.id "
            "GROUP BY i.id ORDER BY i.id DESC"
        ).fetchall()
    return [ImportRecord(id_, name, bank, datetime.fromisoformat(at), count,
                         date.fromisoformat(first) if first else None,
                         date.fromisoformat(last) if last else None)
            for id_, name, bank, at, count, first, last in rows]


def delete_import(db_path: Path, import_id: int):
    """Διαγράφει μία εισαγωγή μαζί με τις γραμμές της. Οι χειροκίνητες κατηγορίες μένουν,
    ώστε να ισχύουν και για τις ίδιες κινήσεις άλλων αρχείων ή αν ξαναγίνει η εισαγωγή."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM imports WHERE id = ?", (import_id,))


# ---------- περιγραφές του χρήστη ----------
# Η αρχική περιγραφή των γραμμών δεν αλλάζει ποτέ· η νέα αποθηκεύεται χωριστά, με κλειδί
# το tx_key, και χρησιμοποιείται μόνο για την εμφάνιση. Οι κατηγορίες και το tx_key
# βασίζονται πάντα στην αρχική.

def load_descriptions(db_path: Path) -> dict[str, str]:
    """Οι περιγραφές που έχει αλλάξει ο χρήστης: tx_key -> νέα περιγραφή."""
    with _connect(db_path) as conn:
        return dict(conn.execute("SELECT tx_key, description FROM custom_descriptions").fetchall())


def set_descriptions(db_path: Path, tx_keys: list[str], description: str):
    with _connect(db_path) as conn:
        conn.executemany("INSERT OR REPLACE INTO custom_descriptions (tx_key, description) VALUES (?, ?)",
                         [(key, description) for key in tx_keys])


def clear_descriptions(db_path: Path, tx_keys: list[str]):
    """Επαναφορά στην αρχική περιγραφή του αρχείου της τράπεζας."""
    with _connect(db_path) as conn:
        conn.executemany("DELETE FROM custom_descriptions WHERE tx_key = ?", [(key,) for key in tx_keys])


# ---------- κατηγορίες ----------

def load_categories(db_path: Path) -> list[CategoryRecord]:
    """Οι κατηγορίες με τη σειρά τους, που είναι και η σειρά ελέγχου των λέξεων-κλειδιών."""
    with _connect(db_path) as conn:
        categories = conn.execute("SELECT id, name, is_income FROM categories ORDER BY position, id").fetchall()
        keywords = defaultdict(list)
        for category_id, keyword in conn.execute(
                "SELECT category_id, keyword FROM category_keywords ORDER BY position, id"):
            keywords[category_id].append(keyword)
    return [CategoryRecord(id_, name, bool(is_income), keywords[id_]) for id_, name, is_income in categories]


def load_manual(db_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Οι χειροκίνητες επιλογές: (tx_key -> κατηγορία, περιγραφή -> κατηγορία)."""
    with _connect(db_path) as conn:
        by_transaction = conn.execute(
            "SELECT m.tx_key, c.name FROM manual_transactions m JOIN categories c ON c.id = m.category_id"
        ).fetchall()
        by_description = conn.execute(
            "SELECT m.description, c.name FROM manual_descriptions m JOIN categories c ON c.id = m.category_id"
        ).fetchall()
    return dict(by_transaction), dict(by_description)


def _category_id(conn: sqlite3.Connection, name: str, income: bool = False) -> int:
    """Το id της κατηγορίας· αν δεν υπάρχει, τη δημιουργεί στο τέλος της λίστας."""
    row = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
    if row:
        if income:
            conn.execute("UPDATE categories SET is_income = 1 WHERE id = ?", (row[0],))
        return row[0]
    return conn.execute(
        "INSERT INTO categories (name, is_income, position) "
        "VALUES (?, ?, (SELECT COALESCE(MAX(position), -1) + 1 FROM categories))",
        (name, income),
    ).lastrowid


def _set_manual(conn: sqlite3.Connection, tx_keys, descriptions, category_id: int):
    conn.executemany("INSERT OR REPLACE INTO manual_transactions (tx_key, category_id) VALUES (?, ?)",
                     [(key, category_id) for key in tx_keys])
    conn.executemany("INSERT OR REPLACE INTO manual_descriptions (description, category_id) VALUES (?, ?)",
                     [(description, category_id) for description in descriptions])


def _clear_transactions(conn: sqlite3.Connection, tx_keys):
    conn.executemany("DELETE FROM manual_transactions WHERE tx_key = ?", [(key,) for key in tx_keys])


def assign_transactions(db_path: Path, tx_keys: list[str], category: str, income: bool = False):
    """Βάζει τις συγκεκριμένες κινήσεις στην κατηγορία, όλες μαζί ή καμία."""
    with _connect(db_path) as conn:
        _set_manual(conn, tx_keys, (), _category_id(conn, category, income))


def assign_descriptions(db_path: Path, descriptions: list[str], tx_keys: list[str], category: str,
                        income: bool = False):
    """Βάζει όλες τις κινήσεις με αυτές τις περιγραφές στην κατηγορία· οι επιλογές
    των tx_keys καταργούνται, γιατί θα είχαν προτεραιότητα."""
    with _connect(db_path) as conn:
        _set_manual(conn, (), descriptions, _category_id(conn, category, income))
        _clear_transactions(conn, tx_keys)


def clear_manual(db_path: Path, tx_keys: list[str], descriptions: list[str]):
    """Καταργεί τις χειροκίνητες επιλογές, ώστε να ισχύει ξανά η αυτόματη κατηγορία."""
    with _connect(db_path) as conn:
        _clear_transactions(conn, tx_keys)
        conn.executemany("DELETE FROM manual_descriptions WHERE description = ?",
                         [(description,) for description in descriptions])


def _check_new_name(conn: sqlite3.Connection, name: str):
    if not name:
        raise ValueError(t("categories.name_empty"))
    if conn.execute("SELECT 1 FROM categories WHERE name = ?", (name,)).fetchone():
        raise ValueError(t("categories.name_exists", name=name))


def _check_not_system(conn: sqlite3.Connection, category_id: int):
    row = conn.execute("SELECT name FROM categories WHERE id = ?", (category_id,)).fetchone()
    if row and row[0] in SYSTEM_CATEGORIES:
        raise ValueError(t("categories.system", name=row[0]))


def add_category(db_path: Path, name: str) -> int:
    with _connect(db_path) as conn:
        _check_new_name(conn, name)
        return _category_id(conn, name)


def rename_category(db_path: Path, category_id: int, name: str):
    """Οι χειροκίνητες επιλογές δείχνουν στο id, οπότε ακολουθούν το νέο όνομα."""
    with _connect(db_path) as conn:
        _check_not_system(conn, category_id)
        _check_new_name(conn, name)
        conn.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))


def set_category_income(db_path: Path, category_id: int, is_income: bool):
    with _connect(db_path) as conn:
        _check_not_system(conn, category_id)
        conn.execute("UPDATE categories SET is_income = ? WHERE id = ?", (is_income, category_id))


def delete_category(db_path: Path, category_id: int):
    """Διαγράφει την κατηγορία· οι κινήσεις της γυρίζουν στην αυτόματη κατηγορία."""
    with _connect(db_path) as conn:
        _check_not_system(conn, category_id)
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))


def move_category(db_path: Path, category_id: int, step: int):
    """Μετακινεί την κατηγορία πάνω (step=-1) ή κάτω (step=1) στη σειρά."""
    with _connect(db_path) as conn:
        ids = [row[0] for row in conn.execute("SELECT id FROM categories ORDER BY position, id")]
        index = ids.index(category_id)
        target = index + step
        if not 0 <= target < len(ids):
            return
        ids[index], ids[target] = ids[target], ids[index]
        conn.executemany("UPDATE categories SET position = ? WHERE id = ?",
                         [(position, id_) for position, id_ in enumerate(ids)])


def set_keywords(db_path: Path, category_id: int, keywords: list[str]):
    """Αντικαθιστά τις λέξεις-κλειδιά της κατηγορίας. Τα κενά τους μένουν ως έχουν,
    γιατί μετράνε στο ταίριασμα (π.χ. «POI » αλλά όχι «POINT»)."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM category_keywords WHERE category_id = ?", (category_id,))
        _insert_keywords(conn, category_id, keywords)


def migrate_manual_file(db_path: Path, path: Path):
    """Μεταφέρει μία φορά τις παλιές επιλογές του manual_categories.json στη βάση.
    Το αρχείο μένει στον δίσκο, αλλά δεν ξαναδιαβάζεται. Σε σφάλμα η βάση μένει ως
    είχε και η μεταφορά θα ξαναδοκιμαστεί στο επόμενο άνοιγμα."""
    with _connect(db_path) as conn:
        if _version(conn) >= VERSION_MANUAL_MIGRATED:
            return
        if path.exists():
            manual = json.loads(path.read_text(encoding="utf-8"))
            for name in manual.get("income_categories", []):
                _category_id(conn, name, income=True)
            for key, name in manual.get("by_transaction", {}).items():
                _set_manual(conn, [key], (), _category_id(conn, name))
            for description, name in manual.get("by_description", {}).items():
                _set_manual(conn, (), [description], _category_id(conn, name))
        conn.execute(f"PRAGMA user_version = {VERSION_MANUAL_MIGRATED}")
