"""Υπολογισμός στατιστικών εσόδων/εξόδων."""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from .categories import Categorizer
from .loader import Transaction

ZERO = Decimal("0")


@dataclass
class MonthStats:
    month: str
    income: Decimal = ZERO
    expenses: Decimal = ZERO  # θετικός αριθμός

    @property
    def net(self) -> Decimal:
        return self.income - self.expenses


@dataclass
class CategoryStats:
    name: str
    total: Decimal = ZERO  # θετικός αριθμός
    count: int = 0


@dataclass
class Stats:
    transactions: list[Transaction]
    categories: dict[Transaction, str]
    income: Decimal = ZERO
    expenses: Decimal = ZERO
    months: list[MonthStats] = field(default_factory=list)
    expense_categories: list[CategoryStats] = field(default_factory=list)
    income_categories: list[CategoryStats] = field(default_factory=list)
    top_merchants: list[CategoryStats] = field(default_factory=list)
    daily_expenses: dict = field(default_factory=dict)

    @property
    def net(self) -> Decimal:
        return self.income - self.expenses

    @property
    def balances(self) -> dict[str, Decimal]:
        """Τελευταίο υπόλοιπο κάθε τράπεζας."""
        result = {}
        for tx in reversed(self.transactions):
            if tx.balance is not None and tx.bank not in result:
                result[tx.bank] = tx.balance
        return result

    @property
    def last_balance(self) -> Decimal | None:
        """Άθροισμα των τελευταίων υπολοίπων όλων των τραπεζών."""
        balances = self.balances
        return sum(balances.values(), ZERO) if balances else None

    @property
    def days(self) -> int:
        if not self.transactions:
            return 0
        return (self.transactions[-1].date - self.transactions[0].date).days + 1

    @property
    def avg_daily_expense(self) -> Decimal:
        return self.expenses / self.days if self.days else ZERO

    @property
    def largest_expense(self) -> Transaction | None:
        expenses = [t for t in self.transactions if not t.is_income]
        return min(expenses, key=lambda t: t.amount) if expenses else None


def _sorted_groups(groups: dict[str, CategoryStats]) -> list[CategoryStats]:
    return sorted(groups.values(), key=lambda c: c.total, reverse=True)


def compute(transactions: list[Transaction], categorizer: Categorizer) -> Stats:
    categories = {t: categorizer.categorize_tx(t) for t in transactions}
    stats = Stats(transactions=transactions, categories=categories)

    months: dict[str, MonthStats] = {}
    exp_cats: dict[str, CategoryStats] = {}
    inc_cats: dict[str, CategoryStats] = {}
    merchants: dict[str, CategoryStats] = {}
    daily = defaultdict(lambda: ZERO)

    for tx in transactions:
        m = months.setdefault(tx.month, MonthStats(tx.month))
        cat = categories[tx]
        if tx.is_income and categorizer.is_income_category(cat):
            stats.income += tx.amount
            m.income += tx.amount
            c = inc_cats.setdefault(cat, CategoryStats(cat))
            c.total += tx.amount
            c.count += 1
        else:
            # Έξοδο, ή επιστροφή χρημάτων (αρνητική τιμή) που μειώνει τα έξοδα.
            value = -tx.amount
            stats.expenses += value
            m.expenses += value
            c = exp_cats.setdefault(cat, CategoryStats(cat))
            c.total += value
            c.count += 1
            mer = merchants.setdefault(tx.description, CategoryStats(tx.description))
            mer.total += value
            mer.count += 1
            daily[tx.date] += value

    stats.months = sorted(months.values(), key=lambda m: m.month)
    stats.expense_categories = _sorted_groups(exp_cats)
    stats.income_categories = _sorted_groups(inc_cats)
    stats.top_merchants = _sorted_groups(merchants)
    stats.daily_expenses = dict(sorted(daily.items()))
    return stats


def fmt(value: Decimal | None) -> str:
    """Μορφοποίηση ποσού στα ελληνικά: 1.234,56 €"""
    if value is None:
        return "-"
    s = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"
