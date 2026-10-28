"""Desktop εφαρμογή (Tkinter + matplotlib) για στατιστικά εσόδων/εξόδων."""

import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.dates  # noqa: E402
import matplotlib.ticker  # noqa: E402
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from .categories import Categorizer  # noqa: E402
from .loader import bank_folders, data_files, load_banks, split_transfers  # noqa: E402
from .stats import Stats, compute, fmt  # noqa: E402

ALL_MONTHS = "Όλοι οι μήνες"
ALL_BANKS = "Όλες οι τράπεζες"

# Χρώματα (σειρά 1 = έσοδα, σειρά 2 = έξοδα)
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_MUTED = "#52514e"
GRID = "#e4e3df"
INCOME = "#2a78d6"
EXPENSE = "#eb6834"


def _style_axes(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT_MUTED, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _euro_formatter(ax, axis="y"):
    formatter = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f} €".replace(",", "."))
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(formatter)


class ChartPanel(ttk.Frame):
    """Ένα γράφημα matplotlib με tooltip στο hover."""

    def __init__(self, master, height=4):
        super().__init__(master)
        self.figure = Figure(figsize=(8, height), dpi=100, facecolor=SURFACE, layout="constrained")
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._hover_items = []  # (artist, κείμενο)
        self._annot = None
        self.canvas.mpl_connect("motion_notify_event", self._on_move)

    def new_axes(self):
        self.figure.clear()
        self._hover_items = []
        ax = self.figure.add_subplot(111)
        _style_axes(ax)
        self._annot = ax.annotate(
            "", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
            fontsize=9, color=TEXT,
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=GRID),
        )
        self._annot.set_visible(False)
        return ax

    def add_hover(self, artist, text):
        self._hover_items.append((artist, text))

    def draw(self):
        self.canvas.draw_idle()

    def _on_move(self, event):
        if self._annot is None:
            return
        visible = self._annot.get_visible()
        if event.inaxes:
            for artist, text in self._hover_items:
                hit, _ = artist.contains(event)
                if hit:
                    self._annot.xy = (event.xdata, event.ydata)
                    self._annot.set_text(text)
                    self._annot.set_visible(True)
                    self.canvas.draw_idle()
                    return
        if visible:
            self._annot.set_visible(False)
            self.canvas.draw_idle()


def make_tree(master, columns, widths, anchors=None):
    frame = ttk.Frame(master)
    tree = ttk.Treeview(frame, columns=[c for c in columns], show="headings")
    for i, (col, width) in enumerate(zip(columns, widths)):
        tree.heading(col, text=col)
        anchor = (anchors or {}).get(i, "w")
        tree.column(col, width=width, anchor=anchor, stretch=(i == 0 or width > 250))
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    tree.tag_configure("income", foreground=INCOME)
    tree.tag_configure("expense", foreground=TEXT)
    tree.tag_configure("total", font=("Segoe UI", 9, "bold"))
    return frame, tree


class CategoryDialog(tk.Toplevel):
    """Παράθυρο επιλογής κατηγορίας για μία ή περισσότερες κινήσεις."""

    def __init__(self, master, txs, categories, current, whole_description=False):
        super().__init__(master)
        self.title("Αλλαγή κατηγορίας")
        self.transient(master)
        self.resizable(False, False)
        self.result = None
        self.categories = categories

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        total = sum(t.amount for t in txs)
        descriptions = sorted({t.description for t in txs})
        summary = f"{len(txs)} κινήσεις · σύνολο {fmt(total)}"
        if len(descriptions) == 1:
            summary = f"{descriptions[0]}\n{summary}"
        ttk.Label(body, text=summary, foreground=TEXT_MUTED).pack(anchor="w", pady=(0, 10))

        ttk.Label(body, text="Κατηγορία (διάλεξε ή γράψε νέα):").pack(anchor="w")
        self.name_var = tk.StringVar(value=current)
        box = ttk.Combobox(body, textvariable=self.name_var, values=categories, width=40)
        box.pack(fill="x", pady=(2, 10))
        box.focus_set()
        box.select_range(0, "end")

        self.whole_var = tk.BooleanVar(value=whole_description)
        ttk.Checkbutton(
            body, variable=self.whole_var,
            text="Όλες οι κινήσεις με την ίδια περιγραφή (και οι μελλοντικές)",
        ).pack(anchor="w")

        self.income_var = tk.BooleanVar(value=all(t.amount > 0 for t in txs))
        self.income_check = ttk.Checkbutton(
            body, variable=self.income_var, text="Νέα κατηγορία εσόδων (όχι εξόδων)",
        )
        self.income_check.pack(anchor="w", pady=(4, 0))
        self.name_var.trace_add("write", lambda *_: self._toggle_income())
        self._toggle_income()

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Άκυρο", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="OK", command=self._ok).pack(side="right", padx=6)
        self.bind("<Return>", lambda _: self._ok())
        self.bind("<Escape>", lambda _: self.destroy())

        self.grab_set()
        self.wait_window()

    def _toggle_income(self):
        is_new = self.name_var.get().strip() not in self.categories
        self.income_check.state(["!disabled"] if is_new else ["disabled"])

    def _ok(self):
        name = self.name_var.get().strip()
        if not name:
            return
        is_new = name not in self.categories
        self.result = (name, self.whole_var.get(), is_new and self.income_var.get())
        self.destroy()


class MyMoneyApp(tk.Tk):
    def __init__(self, files_dir: Path, categories_file: Path, manual_file: Path):
        super().__init__()
        self.files_dir = files_dir
        self.categories_file = categories_file
        self.manual_file = manual_file
        self.tx_items = {}  # iid του πίνακα κινήσεων -> Transaction
        self.title("MyMoney — Έσοδα & Έξοδα")
        self.geometry("1150x780")
        self.minsize(900, 600)
        self.configure(bg=SURFACE)

        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Card.TFrame", background="white", relief="solid", borderwidth=1)
        style.configure("CardTitle.TLabel", background="white", foreground=TEXT_MUTED, font=("Segoe UI", 9))
        style.configure("CardValue.TLabel", background="white", foreground=TEXT, font=("Segoe UI", 15, "bold"))
        style.configure("Treeview", rowheight=24)

        self.all_transactions = []
        self.banks: list[str] = []
        self.stats: Stats | None = None
        self.bank_stats: dict[str, Stats] = {}
        self.transfers = []  # μεταφορές μεταξύ τραπεζών της τρέχουσας περιόδου

        self._build_toolbar()
        self._build_cards()
        self._build_tabs()
        self.reload()

    # ---------- κατασκευή UI ----------

    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=(12, 10))
        bar.pack(fill="x")
        ttk.Label(bar, text="Περίοδος:").pack(side="left")
        self.period_var = tk.StringVar(value=ALL_MONTHS)
        self.period_box = ttk.Combobox(bar, textvariable=self.period_var, state="readonly", width=18)
        self.period_box.pack(side="left", padx=(6, 16))
        self.period_box.bind("<<ComboboxSelected>>", lambda _: self.refresh())

        ttk.Label(bar, text="Τράπεζα:").pack(side="left")
        self.bank_var = tk.StringVar(value=ALL_BANKS)
        self.bank_box = ttk.Combobox(bar, textvariable=self.bank_var, state="readonly", width=20)
        self.bank_box.pack(side="left", padx=(6, 16))
        self.bank_box.bind("<<ComboboxSelected>>", lambda _: self.refresh())

        ttk.Button(bar, text="⟳ Επαναφόρτωση αρχείων", command=self.reload).pack(side="left")
        ttk.Button(bar, text="📂 Φάκελος files", command=self._open_folder).pack(side="left", padx=6)
        ttk.Button(bar, text="✎ Κατηγορίες", command=self._open_categories).pack(side="left")
        self.status_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.status_var, foreground=TEXT_MUTED).pack(side="right")

    def _build_cards(self):
        row = ttk.Frame(self, padding=(12, 0, 12, 8))
        row.pack(fill="x")
        self.card_vars = {}
        titles = ["Έσοδα", "Έξοδα", "Καθαρό αποτέλεσμα", "Τελευταίο υπόλοιπο", "Μέσο έξοδο / ημέρα", "Κινήσεις"]
        for i, title in enumerate(titles):
            card = ttk.Frame(row, style="Card.TFrame", padding=(12, 8))
            card.grid(row=0, column=i, sticky="nsew", padx=4)
            row.columnconfigure(i, weight=1)
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
            var = tk.StringVar(value="-")
            ttk.Label(card, textvariable=var, style="CardValue.TLabel").pack(anchor="w")
            self.card_vars[title] = var

    def _build_tabs(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.notebook = nb

        # Ανά μήνα
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text="Ανά μήνα")
        self.month_chart = ChartPanel(tab, height=3.6)
        self.month_chart.pack(fill="both", expand=True)
        frame, self.month_tree = make_tree(
            tab, ["Μήνας", "Έσοδα", "Έξοδα", "Καθαρό"], [150, 150, 150, 150],
            anchors={1: "e", 2: "e", 3: "e"},
        )
        frame.configure(height=170)
        frame.pack_propagate(False)
        frame.pack(fill="x", pady=(8, 0))

        # Ανά τράπεζα
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text="Ανά τράπεζα")
        self.bank_chart = ChartPanel(tab, height=3.4)
        self.bank_chart.pack(fill="both", expand=True)
        frame, self.bank_tree = make_tree(
            tab, ["Τράπεζα", "Έσοδα", "Έξοδα", "Καθαρό", "Υπόλοιπο", "Κινήσεις"],
            [180, 130, 130, 130, 130, 80], anchors={1: "e", 2: "e", 3: "e", 4: "e", 5: "e"},
        )
        frame.configure(height=150)
        frame.pack_propagate(False)
        frame.pack(fill="x", pady=(8, 0))
        self.bank_tree.bind("<Double-1>", self._on_bank_open)
        self.transfer_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.transfer_var, foreground=TEXT_MUTED,
                  wraplength=1000, justify="left").pack(anchor="w", pady=(4, 0))

        # Κατηγορίες εξόδων
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text="Κατηγορίες εξόδων")
        paned = ttk.PanedWindow(tab, orient="horizontal")
        paned.pack(fill="both", expand=True)
        self.cat_chart = ChartPanel(paned)
        frame, self.cat_tree = make_tree(
            paned, ["Κατηγορία", "Ποσό", "%", "Πλήθος"], [160, 95, 55, 55],
            anchors={1: "e", 2: "e", 3: "e"},
        )
        self.cat_tree.bind("<Double-1>", self._on_category_open)
        paned.add(self.cat_chart, weight=3)
        paned.add(frame, weight=2)
        ttk.Label(tab, text="Διπλό κλικ σε κατηγορία για να δεις τις κινήσεις της.",
                  foreground=TEXT_MUTED).pack(anchor="w", pady=(4, 0))

        # Ημερήσια έξοδα
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text="Ημερήσια έξοδα")
        self.daily_chart = ChartPanel(tab)
        self.daily_chart.pack(fill="both", expand=True)

        # Top δαπάνες ανά έμπορο
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text="Top έμποροι")
        frame, self.merchant_tree = make_tree(
            tab, ["Περιγραφή", "Κατηγορία", "Σύνολο", "Πλήθος", "Μέσος όρος"],
            [320, 200, 120, 70, 120], anchors={2: "e", 3: "e", 4: "e"},
        )
        frame.pack(fill="both", expand=True)
        self.merchant_tree.bind("<Double-1>", self._on_merchant_edit)
        ttk.Label(tab, text="Διπλό κλικ για να βάλεις όλες τις κινήσεις του εμπόρου σε κατηγορία.",
                  foreground=TEXT_MUTED).pack(anchor="w", pady=(4, 0))

        # Κινήσεις
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text="Κινήσεις")
        self.tx_tab = tab
        filters = ttk.Frame(tab)
        filters.pack(fill="x", pady=(0, 6))
        ttk.Label(filters, text="Αναζήτηση:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._fill_transactions())
        ttk.Entry(filters, textvariable=self.search_var, width=30).pack(side="left", padx=6)
        ttk.Label(filters, text="Κατηγορία:").pack(side="left", padx=(12, 0))
        self.cat_filter_var = tk.StringVar(value="Όλες")
        self.cat_filter_box = ttk.Combobox(filters, textvariable=self.cat_filter_var, state="readonly", width=28)
        self.cat_filter_box.pack(side="left", padx=6)
        self.cat_filter_box.bind("<<ComboboxSelected>>", lambda _: self._fill_transactions())
        self.tx_total_var = tk.StringVar()
        ttk.Label(filters, textvariable=self.tx_total_var, foreground=TEXT_MUTED).pack(side="right")
        frame, self.tx_tree = make_tree(
            tab, ["Ημερομηνία", "Τράπεζα", "Περιγραφή", "Κατηγορία", "Ποσό", "Υπόλοιπο"],
            [100, 120, 320, 190, 110, 120], anchors={4: "e", 5: "e"},
        )
        frame.pack(fill="both", expand=True)

        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Αλλαγή κατηγορίας…", command=self._edit_selected).pack(side="left")
        ttk.Button(actions, text="Επαναφορά αυτόματης κατηγορίας",
                   command=self._clear_selected).pack(side="left", padx=6)
        ttk.Label(actions, foreground=TEXT_MUTED,
                  text="Ctrl/Shift + κλικ για πολλές κινήσεις · διπλό ή δεξί κλικ · ✎ = χειροκίνητη κατηγορία",
                  ).pack(side="left", padx=12)

        self.tx_menu = tk.Menu(self, tearoff=False)
        self.tx_menu.add_command(label="Αλλαγή κατηγορίας…", command=self._edit_selected)
        self.tx_menu.add_command(label="Επαναφορά αυτόματης κατηγορίας", command=self._clear_selected)
        self.tx_tree.bind("<Double-1>", lambda _: self._edit_selected())
        self.tx_tree.bind("<Button-3>", self._on_tx_right_click)

    # ---------- δεδομένα ----------

    def reload(self):
        try:
            self.all_transactions = load_banks(self.files_dir)
            self.categorizer = Categorizer.from_file(self.categories_file, self.manual_file)
        except Exception as exc:  # εμφάνιση σφάλματος αντί για crash
            messagebox.showerror("Σφάλμα", f"Αποτυχία ανάγνωσης αρχείων:\n{exc}")
            return
        files = sum(len(data_files(f)) for f in bank_folders(self.files_dir))
        self.banks = sorted({t.bank for t in self.all_transactions})
        self.status_var.set(f"{len(self.banks)} τράπεζες · {files} αρχεία · "
                            f"{len(self.all_transactions)} κινήσεις")
        months = sorted({t.month for t in self.all_transactions}, reverse=True)
        self.period_box["values"] = [ALL_MONTHS, *months]
        if self.period_var.get() not in self.period_box["values"]:
            self.period_var.set(ALL_MONTHS)
        self.bank_box["values"] = [ALL_BANKS, *self.banks]
        if self.bank_var.get() not in self.bank_box["values"]:
            self.bank_var.set(ALL_BANKS)
        self.refresh()

    def refresh(self):
        period = self.period_var.get()
        txs = self.all_transactions
        if period != ALL_MONTHS:
            txs = [t for t in txs if t.month == period]
        # Κάθε τράπεζα ξεχωριστά: οι μεταφορές προς/από άλλες τράπεζες μετράνε κανονικά.
        self.bank_stats = {
            bank: compute([t for t in txs if t.bank == bank], self.categorizer)
            for bank in self.banks
        }
        # Σύνολο: οι μεταφορές μεταξύ των τραπεζών αλληλοαναιρούνται.
        combined, self.transfers = split_transfers(txs)
        self.combined_stats = compute(combined, self.categorizer)
        bank = self.bank_var.get()
        self.stats = self.combined_stats if bank == ALL_BANKS else self.bank_stats[bank]
        self._fill_cards()
        self._fill_months()
        self._fill_banks()
        self._fill_categories()
        self._fill_daily()
        self._fill_merchants()
        cats = sorted(set(self.stats.categories.values()))
        self.cat_filter_box["values"] = ["Όλες", *cats]
        if self.cat_filter_var.get() not in self.cat_filter_box["values"]:
            self.cat_filter_var.set("Όλες")
        self._fill_transactions()

    def _fill_cards(self):
        s = self.stats
        self.card_vars["Έσοδα"].set(fmt(s.income))
        self.card_vars["Έξοδα"].set(fmt(s.expenses))
        self.card_vars["Καθαρό αποτέλεσμα"].set(("+" if s.net > 0 else "") + fmt(s.net))
        self.card_vars["Τελευταίο υπόλοιπο"].set(fmt(s.last_balance))
        self.card_vars["Μέσο έξοδο / ημέρα"].set(fmt(s.avg_daily_expense))
        self.card_vars["Κινήσεις"].set(str(len(s.transactions)))

    def _fill_months(self):
        s = self.stats
        tree = self.month_tree
        tree.delete(*tree.get_children())
        for m in reversed(s.months):
            tree.insert("", "end", values=(m.month, fmt(m.income), fmt(m.expenses), fmt(m.net)))
        if len(s.months) > 1:
            tree.insert("", "end", values=("Σύνολο", fmt(s.income), fmt(s.expenses), fmt(s.net)), tags=("total",))

        chart = self.month_chart
        ax = chart.new_axes()
        if s.months:
            labels = [m.month for m in s.months]
            x = range(len(labels))
            w = 0.38
            inc = ax.bar([i - w / 2 - 0.01 for i in x], [float(m.income) for m in s.months],
                         width=w, color=INCOME, label="Έσοδα")
            exp = ax.bar([i + w / 2 + 0.01 for i in x], [float(m.expenses) for m in s.months],
                         width=w, color=EXPENSE, label="Έξοδα")
            for m, b in zip(s.months, inc):
                chart.add_hover(b, f"{m.month}\nΈσοδα: {fmt(m.income)}")
            for m, b in zip(s.months, exp):
                chart.add_hover(b, f"{m.month}\nΈξοδα: {fmt(m.expenses)}")
            ax.set_xticks(list(x), labels)
            ax.set_xlim(-0.6, max(len(labels) - 0.4, 1.4))
            _euro_formatter(ax)
            top = max(max(m.income, m.expenses) for m in s.months)
            ax.set_ylim(0, float(top) * 1.2 or 1)
            ax.legend(frameon=False, loc="upper right", ncols=2, fontsize=9, labelcolor=TEXT_MUTED)
            ax.set_title("Έσοδα και έξοδα ανά μήνα", loc="left", fontsize=11, color=TEXT)
        chart.draw()

    def _fill_banks(self):
        tree = self.bank_tree
        tree.delete(*tree.get_children())
        rows = [(bank, s) for bank, s in self.bank_stats.items() if s.transactions]
        for bank, s in rows:
            tree.insert("", "end", values=(bank, fmt(s.income), fmt(s.expenses), fmt(s.net),
                                           fmt(s.last_balance), len(s.transactions)))
        if len(rows) > 1:
            total = self.combined_stats
            tree.insert("", "end", values=("Σύνολο", fmt(total.income), fmt(total.expenses),
                                           fmt(total.net), fmt(total.last_balance),
                                           len(total.transactions)), tags=("total",))

        hint = "Διπλό κλικ σε τράπεζα για να δεις μόνο αυτή."
        if self.transfers:
            moved = sum(t.amount for t in self.transfers if t.amount > 0)
            hint = (f"{len(self.transfers) // 2} μεταφορές μεταξύ των τραπεζών ({fmt(moved)}) "
                    "δεν μετρούν ως έσοδα/έξοδα στο σύνολο, μόνο στην κάθε τράπεζα. " + hint)
        self.transfer_var.set(hint)

        chart = self.bank_chart
        ax = chart.new_axes()
        if rows:
            labels = [bank for bank, _ in rows]
            x = range(len(labels))
            w = 0.38
            inc = ax.bar([i - w / 2 - 0.01 for i in x], [float(s.income) for _, s in rows],
                         width=w, color=INCOME, label="Έσοδα")
            exp = ax.bar([i + w / 2 + 0.01 for i in x], [float(s.expenses) for _, s in rows],
                         width=w, color=EXPENSE, label="Έξοδα")
            for (bank, s), b in zip(rows, inc):
                chart.add_hover(b, f"{bank}\nΈσοδα: {fmt(s.income)}")
            for (bank, s), b in zip(rows, exp):
                chart.add_hover(b, f"{bank}\nΈξοδα: {fmt(s.expenses)}")
            ax.set_xticks(list(x), labels)
            ax.set_xlim(-0.6, max(len(labels) - 0.4, 1.4))
            _euro_formatter(ax)
            top = max(max(s.income, s.expenses) for _, s in rows)
            ax.set_ylim(0, float(top) * 1.2 or 1)
            ax.legend(frameon=False, loc="upper right", ncols=2, fontsize=9, labelcolor=TEXT_MUTED)
            ax.set_title("Έσοδα και έξοδα ανά τράπεζα", loc="left", fontsize=11, color=TEXT)
        chart.draw()

    def _on_bank_open(self, _event):
        sel = self.bank_tree.selection()
        if not sel:
            return
        name = self.bank_tree.item(sel[0], "values")[0]
        self.bank_var.set(name if name in self.banks else ALL_BANKS)
        self.refresh()

    def _fill_categories(self):
        s = self.stats
        tree = self.cat_tree
        tree.delete(*tree.get_children())
        for c in s.expense_categories:
            pct = (c.total / s.expenses * 100) if s.expenses else 0
            tree.insert("", "end", values=(c.name, fmt(c.total), f"{pct:.1f}%", c.count))
        for c in s.income_categories:
            tree.insert("", "end", values=(c.name, "+" + fmt(c.total), "", c.count), tags=("income",))

        chart = self.cat_chart
        ax = chart.new_axes()
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        cats = list(reversed(s.expense_categories))
        if cats:
            bars = ax.barh([c.name for c in cats], [float(c.total) for c in cats],
                           color=EXPENSE, height=0.6)
            for c, b in zip(cats, bars):
                pct = c.total / s.expenses * 100
                chart.add_hover(b, f"{c.name}\n{fmt(c.total)} · {pct:.1f}% · {c.count} κινήσεις")
                ax.text(b.get_width(), b.get_y() + b.get_height() / 2, f"  {fmt(c.total)}",
                        va="center", fontsize=8, color=TEXT_MUTED)
            ax.set_xlim(0, max(float(cats[-1].total), 1) * 1.25)
            _euro_formatter(ax, "x")
            ax.set_title("Έξοδα ανά κατηγορία", loc="left", fontsize=11, color=TEXT)
        chart.draw()

    def _fill_daily(self):
        chart = self.daily_chart
        ax = chart.new_axes()
        daily = self.stats.daily_expenses
        if daily:
            days = list(daily)
            bars = ax.bar(days, [float(v) for v in daily.values()], color=EXPENSE, width=0.7)
            for d, b in zip(days, bars):
                chart.add_hover(b, f"{d:%d/%m/%Y}\n{fmt(daily[d])}")
            avg = float(self.stats.avg_daily_expense)
            ax.axhline(avg, color=TEXT_MUTED, linewidth=1, linestyle="--")
            ax.text(days[0], avg, f" μέσος όρος {fmt(self.stats.avg_daily_expense)}",
                    va="bottom", fontsize=8, color=TEXT_MUTED)
            ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d/%m"))
            _euro_formatter(ax)
            ax.set_title("Έξοδα ανά ημέρα", loc="left", fontsize=11, color=TEXT)
        chart.draw()

    def _fill_merchants(self):
        s = self.stats
        tree = self.merchant_tree
        tree.delete(*tree.get_children())
        cat_of = {t.description: s.categories[t] for t in s.transactions}
        for m in s.top_merchants:
            tree.insert("", "end", values=(m.name, cat_of.get(m.name, ""), fmt(m.total),
                                           m.count, fmt(m.total / m.count)))

    def _fill_transactions(self):
        if self.stats is None:
            return
        query = self.search_var.get().casefold().strip()
        cat = self.cat_filter_var.get()
        tree = self.tx_tree
        tree.delete(*tree.get_children())
        self.tx_items = {}
        total = 0
        count = 0
        for t in reversed(self.stats.transactions):
            tcat = self.stats.categories[t]
            if cat != "Όλες" and tcat != cat:
                continue
            if query and query not in t.description.casefold():
                continue
            total += t.amount
            count += 1
            shown_cat = f"✎ {tcat}" if self.categorizer.is_manual(t) else tcat
            iid = tree.insert("", "end", values=(f"{t.date:%d/%m/%Y}", t.bank, t.description,
                                                 shown_cat, fmt(t.amount), fmt(t.balance)),
                              tags=("income" if t.is_income else "expense",))
            self.tx_items[iid] = t
        self.tx_total_var.set(f"{count} κινήσεις · σύνολο {fmt(total)}")

    # ---------- χειροκίνητες κατηγορίες ----------

    def _selected_transactions(self):
        return [self.tx_items[iid] for iid in self.tx_tree.selection() if iid in self.tx_items]

    def _on_tx_right_click(self, event):
        row = self.tx_tree.identify_row(event.y)
        if row and row not in self.tx_tree.selection():
            self.tx_tree.selection_set(row)
        if self.tx_tree.selection():
            self.tx_menu.tk_popup(event.x_root, event.y_root)

    def _assign_dialog(self, txs, whole_description=False):
        if not txs:
            messagebox.showinfo("Κατηγορία", "Διάλεξε πρώτα μία ή περισσότερες κινήσεις.")
            return
        current = {self.stats.categories[t] for t in txs}
        dialog = CategoryDialog(
            self, txs, self.categorizer.all_categories(),
            current.pop() if len(current) == 1 else "", whole_description,
        )
        if dialog.result is None:
            return
        name, whole, income = dialog.result
        self.categorizer.assign(txs, name, whole, income)
        self.refresh()

    def _edit_selected(self):
        self._assign_dialog(self._selected_transactions())

    def _clear_selected(self):
        txs = self._selected_transactions()
        if txs:
            self.categorizer.clear(txs)
            self.refresh()

    def _on_merchant_edit(self, _event):
        sel = self.merchant_tree.selection()
        if not sel:
            return
        description = self.merchant_tree.item(sel[0], "values")[0]
        txs = [t for t in self.stats.transactions if t.description == description]
        self._assign_dialog(txs, whole_description=True)

    # ---------- ενέργειες ----------

    def _on_category_open(self, _event):
        sel = self.cat_tree.selection()
        if not sel:
            return
        name = self.cat_tree.item(sel[0], "values")[0]
        self.cat_filter_var.set(name)
        self.search_var.set("")
        self._fill_transactions()
        self.notebook.select(self.tx_tab)

    def _open_folder(self):
        self.files_dir.mkdir(exist_ok=True)
        os.startfile(self.files_dir)

    def _open_categories(self):
        if self.categories_file.exists():
            os.startfile(self.categories_file)
            messagebox.showinfo("Κατηγορίες",
                                "Αφού αποθηκεύσεις τις αλλαγές στο categories.json, "
                                "πάτα «Επαναφόρτωση αρχείων».")
