"""Μεταφράσεις (ελληνικά / αγγλικά) και μορφοποίηση ποσών ανά γλώσσα.

Η γλώσσα αποθηκεύεται στο settings.json (βλ. settings.py)· προεπιλογή τα ελληνικά.
"""

from decimal import Decimal
from pathlib import Path

from . import settings

LANGUAGES = {"el": "Ελληνικά", "en": "English"}
DEFAULT_LANGUAGE = "el"

_language = DEFAULT_LANGUAGE

STRINGS = {
    # Τράπεζες (κλειδί = όνομα τράπεζας στη βάση, σε πεζά)
    "bank.eurobank": ("Eurobank", "Eurobank"),
    "bank.nationalbank": ("Εθνική Τράπεζα", "National Bank of Greece"),
    "bank.piraeus": ("Πειραιώς", "Piraeus Bank"),

    # Γραμμή εργαλείων
    "app.title": ("Οι παράδες μου — Έσοδα & Έξοδα", "MyMoney — Income & Expenses"),
    "toolbar.year": ("Έτος:", "Year:"),
    "toolbar.month": ("Μήνας:", "Month:"),
    "toolbar.bank": ("Τράπεζα:", "Bank:"),
    "theme.to_dark": ("☾ Σκοτεινό", "☾ Dark"),
    "theme.to_light": ("☀ Φωτεινό", "☀ Light"),
    "toolbar.import": ("📥 Εισαγωγή αρχείων…", "📥 Import files…"),
    "toolbar.imports": ("🗂 Εισαγωγές", "🗂 Imports"),
    "toolbar.reload": ("⟳ Επαναφόρτωση", "⟳ Reload"),
    "toolbar.categories": ("✎ Κατηγορίες", "✎ Categories"),
    "status": ("{banks} τράπεζες · {files} αρχεία · {count} κινήσεις",
               "{banks} banks · {files} files · {count} transactions"),
    "status.empty": ("Δεν υπάρχουν κινήσεις. Πάτα «Εισαγωγή αρχείων» για να προσθέσεις τις εξαγωγές των τραπεζών σου.",
                     "No transactions yet. Press “Import files” to add your bank exports."),
    "all_years": ("Όλα τα έτη", "All years"),
    "all_months": ("Όλοι οι μήνες", "All months"),
    "all_time": ("Όλη η περίοδος", "All time"),
    "all_banks": ("Όλες οι τράπεζες", "All banks"),
    "all_categories": ("Όλες", "All"),

    # Κάρτες
    "card.income": ("Έσοδα", "Income"),
    "card.expenses": ("Έξοδα", "Expenses"),
    "card.net": ("Καθαρό αποτέλεσμα", "Net result"),
    "card.balance": ("Τελευταίο υπόλοιπο", "Latest balance"),
    "card.avg_daily": ("Μέσο έξοδο / ημέρα", "Avg. expense / day"),
    "card.count": ("Κινήσεις", "Transactions"),

    # Καρτέλες
    "tab.years": ("Ανά έτος", "By year"),
    "tab.months": ("Ανά μήνα", "By month"),
    "tab.banks": ("Ανά τράπεζα", "By bank"),
    "tab.categories": ("Κατηγορίες εξόδων", "Expense categories"),
    "tab.daily": ("Ημερήσια έξοδα", "Daily expenses"),
    "tab.merchants": ("Top έμποροι", "Top merchants"),
    "tab.transactions": ("Κινήσεις", "Transactions"),

    # Στήλες πινάκων
    "col.year": ("Έτος", "Year"),
    "col.month": ("Μήνας", "Month"),
    "col.months": ("Μήνες", "Months"),
    "col.avg_monthly": ("Μέσο έξοδο / μήνα", "Avg. expense / month"),
    "col.income": ("Έσοδα", "Income"),
    "col.expenses": ("Έξοδα", "Expenses"),
    "col.net": ("Καθαρό", "Net"),
    "col.bank": ("Τράπεζα", "Bank"),
    "col.balance": ("Υπόλοιπο", "Balance"),
    "col.transactions": ("Κινήσεις", "Transactions"),
    "col.category": ("Κατηγορία", "Category"),
    "col.amount": ("Ποσό", "Amount"),
    "col.count": ("Πλήθος", "Count"),
    "col.description": ("Περιγραφή", "Description"),
    "col.total": ("Σύνολο", "Total"),
    "col.average": ("Μέσος όρος", "Average"),
    "col.date": ("Ημερομηνία", "Date"),
    "col.file": ("Αρχείο", "File"),
    "col.imported_at": ("Εισαγωγή", "Imported"),
    "total": ("Σύνολο", "Total"),

    # Υποδείξεις
    "hint.bank_open": ("Διπλό κλικ σε τράπεζα για να δεις μόνο αυτή.",
                       "Double-click a bank to see only that bank."),
    "hint.transfers": ("{count} μεταφορές μεταξύ των τραπεζών ({amount}) δεν μετρούν ως "
                       "έσοδα/έξοδα στο σύνολο, μόνο στην κάθε τράπεζα. ",
                       "{count} transfers between your banks ({amount}) are not counted as "
                       "income/expenses in the total, only in each bank. "),
    "hint.categories": ("Διπλό κλικ σε κατηγορία για να δεις τις κινήσεις της.",
                        "Double-click a category to see its transactions."),
    "hint.merchants": ("Διπλό κλικ για να βάλεις όλες τις κινήσεις του εμπόρου σε κατηγορία.",
                       "Double-click to put all of a merchant's transactions in a category."),
    "hint.transactions": ("Ctrl/Shift + κλικ για πολλές κινήσεις · διπλό ή δεξί κλικ · "
                          "✎ = χειροκίνητη κατηγορία",
                          "Ctrl/Shift + click for multiple transactions · double or right click · "
                          "✎ = manual category"),

    # Κινήσεις
    "tx.search": ("Αναζήτηση:", "Search:"),
    "tx.category": ("Κατηγορία:", "Category:"),
    "tx.summary": ("{count} κινήσεις · σύνολο {total}", "{count} transactions · total {total}"),
    "tx.change_category": ("Αλλαγή κατηγορίας…", "Change category…"),
    "tx.reset_category": ("Επαναφορά αυτόματης κατηγορίας", "Reset to automatic category"),

    # Γραφήματα
    "chart.years": ("Έσοδα και έξοδα ανά έτος", "Income and expenses by year"),
    "chart.months": ("Έσοδα και έξοδα ανά μήνα", "Income and expenses by month"),
    "chart.banks": ("Έσοδα και έξοδα ανά τράπεζα", "Income and expenses by bank"),
    "chart.categories": ("Έξοδα ανά κατηγορία", "Expenses by category"),
    "chart.daily": ("Έξοδα ανά ημέρα", "Expenses by day"),
    "chart.average": (" μέσος όρος {amount}", " average {amount}"),
    "hover.income": ("Έσοδα: {amount}", "Income: {amount}"),
    "hover.expenses": ("Έξοδα: {amount}", "Expenses: {amount}"),
    "hover.category": ("{amount} · {pct}% · {count} κινήσεις", "{amount} · {pct}% · {count} transactions"),

    # Παράθυρο κατηγορίας
    "dialog.title": ("Αλλαγή κατηγορίας", "Change category"),
    "dialog.prompt": ("Κατηγορία (διάλεξε ή γράψε νέα):", "Category (pick one or type a new one):"),
    "dialog.whole": ("Όλες οι κινήσεις με την ίδια περιγραφή (και οι μελλοντικές)",
                     "All transactions with the same description (including future ones)"),
    "dialog.income": ("Νέα κατηγορία εσόδων (όχι εξόδων)", "New income category (not expenses)"),
    "dialog.cancel": ("Άκυρο", "Cancel"),
    "dialog.ok": ("OK", "OK"),

    # Εισαγωγή αρχείων
    "import.title": ("Εισαγωγή αρχείων", "Import files"),
    "import.filetype": ("Εξαγωγές τραπεζών", "Bank exports"),
    "import.prompt": ("Διάλεξε την τράπεζα κάθε αρχείου ή γράψε νέα:",
                      "Pick the bank of each file or type a new one:"),
    "import.ok": ("Εισαγωγή", "Import"),
    "import.result": ("{file} → {bank}: {added} νέες κινήσεις ({rows} γραμμές στο αρχείο)",
                      "{file} → {bank}: {added} new transactions ({rows} rows in the file)"),
    "imports.title": ("Εισαγωγές", "Imports"),
    "imports.delete": ("Διαγραφή εισαγωγής", "Delete import"),
    "imports.close": ("Κλείσιμο", "Close"),
    "imports.confirm": ("Να διαγραφούν οι κινήσεις των αρχείων που διάλεξες από τη βάση;\n{files}",
                        "Delete the transactions of the selected files from the database?\n{files}"),

    # Μηνύματα
    "msg.error": ("Σφάλμα", "Error"),
    "msg.load_failed": ("Αποτυχία ανάγνωσης δεδομένων:\n{error}", "Could not read the data:\n{error}"),
    "msg.category": ("Κατηγορία", "Category"),
    "msg.select_first": ("Διάλεξε πρώτα μία ή περισσότερες κινήσεις.",
                         "Select one or more transactions first."),
    "msg.categories": ("Κατηγορίες", "Categories"),
    "msg.categories_reload": ("Αφού αποθηκεύσεις τις αλλαγές στο categories.json, "
                              "πάτα «Επαναφόρτωση».",
                              "After saving your changes to categories.json, "
                              "press “Reload”."),

    # Σφάλματα ανάγνωσης
    "error.missing_columns": ("{file}: λείπουν οι στήλες {columns}", "{file}: missing columns {columns}"),
    "error.unknown_xlsx": ("άγνωστη μορφή αρχείου xlsx", "unknown xlsx format"),
    "error.no_transactions": ("δεν βρέθηκαν κινήσεις στο αρχείο", "no transactions found in the file"),
    "error.already_imported": ("το αρχείο έχει ήδη εισαχθεί (τράπεζα: {bank})",
                               "this file has already been imported (bank: {bank})"),

    # Αναφορά τερματικού
    "cli.description": ("Στατιστικά εσόδων/εξόδων", "Income/expense statistics"),
    "cli.report": ("εκτύπωση αναφοράς αντί για παράθυρο", "print a report instead of opening the window"),
    "cli.month": ("φίλτρο μήνα, π.χ. 09 (με --year) ή 2026-09", "month filter, e.g. 09 (with --year) or 2026-09"),
    "report.bad_month": ("Μη έγκυρος μήνας «{month}». Δώσε π.χ. 09 ή 2026-09.",
                         "Invalid month “{month}”. Use e.g. 09 or 2026-09."),
    "cli.year": ("φίλτρο έτους για την αναφορά, π.χ. 2026", "year filter for the report, e.g. 2026"),
    "cli.bank": ("μόνο μία τράπεζα, π.χ. eurobank ή nationalbank· με --import, η τράπεζα των αρχείων",
                 "a single bank, e.g. eurobank or nationalbank; with --import, the bank of the files"),
    "cli.import": ("εισαγωγή αρχείων τράπεζας στη βάση", "import bank files into the database"),
    "report.empty": ("Δεν υπάρχουν κινήσεις στη βάση. Κάνε εισαγωγή με --import ΑΡΧΕΙΟ.",
                     "There are no transactions in the database. Import some with --import FILE."),
    "cli.lang": ("γλώσσα (el ή en)· αποθηκεύεται για τις επόμενες φορές",
                 "language (el or en); remembered for next time"),
    "report.unknown_bank": ("Άγνωστη τράπεζα «{bank}». Διαθέσιμες: {banks}",
                            "Unknown bank “{bank}”. Available: {banks}"),
    "report.by_bank": ("Ανά τράπεζα", "By bank"),
    "report.bank_line": ("έσοδα {income}  έξοδα {expenses}  υπόλοιπο {balance}",
                         "income {income}  expenses {expenses}  balance {balance}"),
    "report.transfers": ("({count} μεταφορές μεταξύ τραπεζών, {amount}, εκτός συνόλου)",
                         "({count} transfers between banks, {amount}, excluded from the total)"),
    "report.count": ("Κινήσεις: {count}  ({bank}, {period})", "Transactions: {count}  ({bank}, {period})"),
    "report.income": ("Έσοδα:", "Income:"),
    "report.expenses": ("Έξοδα:", "Expenses:"),
    "report.net": ("Καθαρό:", "Net:"),
    "report.balance": ("Υπόλοιπο:", "Balance:"),
    "report.avg_daily": ("Μέσο έξοδο/ημέρα: {amount}", "Avg. expense/day: {amount}"),
    "report.years": ("Ανά έτος", "By year"),
    "report.year_line": ("έσοδα {income}  έξοδα {expenses}  καθαρό {net}  μέσο έξοδο/μήνα {avg}",
                         "income {income}  expenses {expenses}  net {net}  avg. expense/month {avg}"),
    "report.months": ("Ανά μήνα", "By month"),
    "report.month_line": ("έσοδα {income}  έξοδα {expenses}  καθαρό {net}",
                          "income {income}  expenses {expenses}  net {net}"),
    "report.categories": ("Έξοδα ανά κατηγορία", "Expenses by category"),
    "report.top": ("Top 10 έμποροι", "Top 10 merchants"),
}


MONTH_NAMES = {
    "el": ("Ιανουάριος", "Φεβρουάριος", "Μάρτιος", "Απρίλιος", "Μάιος", "Ιούνιος",
           "Ιούλιος", "Αύγουστος", "Σεπτέμβριος", "Οκτώβριος", "Νοέμβριος", "Δεκέμβριος"),
    "en": ("January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"),
}


def month_name(month: str) -> str:
    """Όνομα μήνα από τον αριθμό του («09» -> «Σεπτέμβριος»)."""
    return MONTH_NAMES[_language][int(month) - 1]


def period_label(year: str | None, month: str | None) -> str:
    """π.χ. «Σεπτέμβριος 2026», «2026», «Σεπτέμβριος» ή «Όλη η περίοδος»."""
    parts = [month_name(month) if month else None, year]
    return " ".join(p for p in parts if p) or t("all_time")


def get_language() -> str:
    return _language


def set_language(language: str):
    global _language
    _language = language if language in LANGUAGES else DEFAULT_LANGUAGE


def t(key: str, **kwargs) -> str:
    """Το κείμενο του key στην τρέχουσα γλώσσα (με αντικατάσταση {πεδίων})."""
    el, en = STRINGS[key]
    text = en if _language == "en" else el
    return text.format(**kwargs) if kwargs else text


def bank_label(bank: str) -> str:
    """Εμφανιζόμενο όνομα τράπεζας από το όνομά της στη βάση."""
    key = f"bank.{bank.casefold()}"
    return t(key) if key in STRINGS else bank


def known_banks() -> list[str]:
    """Οι τράπεζες που έχουν εμφανιζόμενο όνομα στο STRINGS."""
    return [key.removeprefix("bank.") for key in STRINGS if key.startswith("bank.")]


def bank_key(name: str, banks=()) -> str:
    """Το όνομα τράπεζας για τη βάση από ό,τι έγραψε ο χρήστης (όνομα ή εμφανιζόμενο όνομα)·
    banks είναι οι τράπεζες που υπάρχουν ήδη. Μια νέα τράπεζα μένει όπως γράφτηκε."""
    name = name.strip()
    for bank in [*banks, *known_banks()]:
        if name.casefold() in (bank.casefold(), bank_label(bank).casefold()):
            return bank
    return name


def fmt_money(value: Decimal | float | None, decimals: int = 2) -> str:
    """Ποσό σε ευρώ: «1.234,56 €» στα ελληνικά, «€1,234.56» στα αγγλικά."""
    if value is None:
        return "-"
    s = f"{abs(value):,.{decimals}f}"
    sign = "-" if value < 0 else ""
    if _language == "en":
        return f"{sign}€{s}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sign}{s} €"


def load_settings(path: Path):
    set_language(settings.read(path).get("language", DEFAULT_LANGUAGE))


def save_settings(path: Path):
    settings.update(path, language=_language)
