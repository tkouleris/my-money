"""Κατηγοριοποίηση κινήσεων.

Σειρά προτεραιότητας:
1. Χειροκίνητη κατηγορία για τη συγκεκριμένη κίνηση (manual_categories.json)
2. Χειροκίνητη κατηγορία για όλες τις κινήσεις με την ίδια περιγραφή
3. Λέξεις-κλειδιά από το categories.json
"""

import json
from pathlib import Path

from .loader import Transaction

INCOME_OTHER = "Λοιπά έσοδα"
EXPENSE_OTHER = "Λοιπά έξοδα"


def tx_key(tx: Transaction) -> str:
    """Σταθερό αναγνωριστικό κίνησης για αποθήκευση χειροκίνητων επιλογών."""
    return f"{tx.date:%Y-%m-%d}|{tx.value_date:%Y-%m-%d}|{tx.description}|{tx.amount}"


class Categorizer:
    def __init__(self, rules: dict[str, list[str]], income_categories: list[str] = ()):
        self.rules = [
            (name, [k.casefold() for k in keywords]) for name, keywords in rules.items()
        ]
        self.income_categories = {*income_categories, INCOME_OTHER}
        self.manual_path: Path | None = None
        self.by_transaction: dict[str, str] = {}
        self.by_description: dict[str, str] = {}
        self.manual_income: set[str] = set()

    @classmethod
    def from_file(cls, path: Path, manual_path: Path | None = None) -> "Categorizer":
        data = {}
        if path.exists():
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        categorizer = cls(data.get("categories", {}), data.get("income_categories", []))
        if manual_path is not None:
            categorizer.manual_path = manual_path
            if manual_path.exists():
                with manual_path.open(encoding="utf-8") as f:
                    manual = json.load(f)
                categorizer.by_transaction = manual.get("by_transaction", {})
                categorizer.by_description = manual.get("by_description", {})
                categorizer.manual_income = set(manual.get("income_categories", []))
                categorizer.income_categories |= categorizer.manual_income
        return categorizer

    def save_manual(self):
        if self.manual_path is None:
            return
        data = {
            "by_transaction": self.by_transaction,
            "by_description": self.by_description,
            "income_categories": sorted(self.manual_income),
        }
        with self.manual_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

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
        for tx in txs:
            if whole_description:
                self.by_description[tx.description] = category
                self.by_transaction.pop(tx_key(tx), None)
            else:
                self.by_transaction[tx_key(tx)] = category
        if income:
            self.manual_income.add(category)
            self.income_categories.add(category)
        self.save_manual()

    def clear(self, txs: list[Transaction]):
        """Επαναφορά στην αυτόματη κατηγορία (λέξεις-κλειδιά)."""
        for tx in txs:
            self.by_transaction.pop(tx_key(tx), None)
            self.by_description.pop(tx.description, None)
        self.save_manual()

    def all_categories(self) -> list[str]:
        names = [name for name, _ in self.rules]
        for extra in [*self.by_description.values(), *self.by_transaction.values(),
                      *sorted(self.income_categories), EXPENSE_OTHER]:
            if extra not in names:
                names.append(extra)
        return names

    def is_income_category(self, name: str) -> bool:
        """Θετικό ποσό σε κατηγορία εξόδων (π.χ. SKROUTZ) είναι επιστροφή
        χρημάτων και μειώνει τα έξοδα· δεν μετράει ως έσοδο."""
        return name in self.income_categories
