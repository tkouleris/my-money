"""Κατηγοριοποίηση κινήσεων.

Σειρά προτεραιότητας:
1. Χειροκίνητη κατηγορία για τη συγκεκριμένη κίνηση
2. Χειροκίνητη κατηγορία για όλες τις κινήσεις με την ίδια περιγραφή
3. Λέξεις-κλειδιά των κατηγοριών

Όλα αποθηκεύονται στη βάση (database.py).
"""

from pathlib import Path

from . import database
from .default_categories import EXPENSE_OTHER, INCOME_OTHER
from .loader import Transaction


def tx_key(tx: Transaction) -> str:
    """Σταθερό αναγνωριστικό κίνησης για αποθήκευση χειροκίνητων επιλογών."""
    return f"{tx.date:%Y-%m-%d}|{tx.value_date:%Y-%m-%d}|{tx.description}|{tx.amount}"


class Categorizer:
    def __init__(self, db_path: Path, rules: dict[str, list[str]], income_categories: list[str] = ()):
        self.db_path = db_path
        self.rules = [
            (name, [k.casefold() for k in keywords]) for name, keywords in rules.items()
        ]
        self.income_categories = {*income_categories, INCOME_OTHER}
        self.by_transaction: dict[str, str] = {}
        self.by_description: dict[str, str] = {}

    @classmethod
    def from_db(cls, db_path: Path) -> "Categorizer":
        records = database.load_categories(db_path)
        categorizer = cls(db_path, {record.name: record.keywords for record in records},
                          [record.name for record in records if record.is_income])
        categorizer.by_transaction, categorizer.by_description = database.load_manual(db_path)
        return categorizer

    def categorize(self, description: str, is_income: bool) -> str:
        text = description.casefold()
        for name, keywords in self.rules:
            if any(k in text for k in keywords):
                return name
        return INCOME_OTHER if is_income else EXPENSE_OTHER

    def categorize_tx(self, tx: Transaction) -> str:
        key = tx_key(tx)
        if key in self.by_transaction:
            return self.by_transaction[key]
        if tx.description in self.by_description:
            return self.by_description[tx.description]
        return self.categorize(tx.description, tx.is_income)

    def is_manual(self, tx: Transaction) -> bool:
        return tx_key(tx) in self.by_transaction or tx.description in self.by_description

    def assign(self, txs: list[Transaction], category: str, whole_description: bool,
               income: bool = False):
        """Βάζει τις κινήσεις στην κατηγορία. Με whole_description=True ισχύει
        για όλες τις κινήσεις (και μελλοντικές) με την ίδια περιγραφή."""
        keys = [tx_key(tx) for tx in txs]
        if whole_description:
            descriptions = [tx.description for tx in txs]
            database.assign_descriptions(self.db_path, descriptions, keys, category, income)
            self.by_description.update(dict.fromkeys(descriptions, category))
            for key in keys:
                self.by_transaction.pop(key, None)
        else:
            database.assign_transactions(self.db_path, keys, category, income)
            self.by_transaction.update(dict.fromkeys(keys, category))
        if category not in self.all_categories():
            self.rules.append((category, []))
        if income:
            self.income_categories.add(category)

    def clear(self, txs: list[Transaction]):
        """Επαναφορά στην αυτόματη κατηγορία (λέξεις-κλειδιά)."""
        keys = [tx_key(tx) for tx in txs]
        descriptions = [tx.description for tx in txs]
        database.clear_manual(self.db_path, keys, descriptions)
        for key in keys:
            self.by_transaction.pop(key, None)
        for description in descriptions:
            self.by_description.pop(description, None)

    def all_categories(self) -> list[str]:
        return [name for name, _ in self.rules]

    def is_income_category(self, name: str) -> bool:
        """Θετικό ποσό σε κατηγορία εξόδων (π.χ. SKROUTZ) είναι επιστροφή
        χρημάτων και μειώνει τα έξοδα· δεν μετράει ως έσοδο."""
        return name in self.income_categories
