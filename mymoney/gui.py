"""Desktop εφαρμογή (Tkinter + matplotlib) για στατιστικά εσόδων/εξόδων."""

import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.dates  # noqa: E402
import matplotlib.ticker  # noqa: E402
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from . import database, i18n, theme  # noqa: E402
from .categories import Categorizer  # noqa: E402
from .i18n import bank_key, bank_label, fmt_money, known_banks, month_name, t  # noqa: E402
from .loader import SUPPORTED_SUFFIXES, detect_bank, split_transfers  # noqa: E402
from .stats import Stats, compute, fmt  # noqa: E402
from .theme import palette as colors  # noqa: E402

# Λογότυπα τραπεζών 20x20: assets/banks/<όνομα τράπεζας>.png
BANK_LOGOS = Path(__file__).resolve().parent / "assets" / "banks"

def _style_axes(ax):
    ax.set_facecolor(colors().surface)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(colors().grid)
    ax.tick_params(colors=colors().text_muted, labelsize=9, length=0)
    ax.grid(axis="y", color=colors().grid, linewidth=0.8)
    ax.set_axisbelow(True)


def _euro_formatter(ax, axis="y"):
    formatter = matplotlib.ticker.FuncFormatter(lambda v, _: fmt_money(v, decimals=0))
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(formatter)


class ChartPanel(ttk.Frame):
    """Ένα γράφημα matplotlib με tooltip στο hover."""

    def __init__(self, master, height=4):
        super().__init__(master)
        self.figure = Figure(figsize=(8, height), dpi=100, facecolor=colors().surface,
                             layout="constrained")
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
            fontsize=9, color=colors().text,
            bbox=dict(boxstyle="round,pad=0.4", fc=colors().card, ec=colors().grid),
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
    """Πίνακας με στήλες· columns είναι κλειδιά μετάφρασης (col.*)."""
    frame = ttk.Frame(master)
    tree = ttk.Treeview(frame, columns=list(columns), show="headings")
    for i, (col, width) in enumerate(zip(columns, widths)):
        tree.heading(col, text=t(col) if col in i18n.STRINGS else col)
        anchor = (anchors or {}).get(i, "w")
        tree.column(col, width=width, anchor=anchor, stretch=(i == 0 or width > 250))
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    tree.tag_configure("income", foreground=colors().income)
    tree.tag_configure("expense", foreground=colors().text)
    tree.tag_configure("total", font=theme.font(9, "bold"))
    return frame, tree


def run_modal(dialog: tk.Toplevel):
    """Κάνει τον διάλογο modal και περιμένει να κλείσει.

    Στο X11 το grab αποτυγχάνει αν το παράθυρο δεν έχει εμφανιστεί και το κουμπί του
    ποντικιού είναι ακόμα πατημένο, όπως όταν ο διάλογος ανοίγει με διπλό κλικ."""
    theme.style_title_bar(dialog)
    dialog.wait_visibility()
    dialog.grab_set()
    dialog.wait_window()


class IconDropdown(ttk.Menubutton):
    """Λίστα επιλογής με εικονίδιο σε κάθε επιλογή.

    Το Combobox δεν δείχνει εικόνες και τα μενού των Windows αγνοούν τα χρώματα του
    θέματος, οπότε η λίστα είναι ένα Treeview σε αναδυόμενο παράθυρο."""

    def __init__(self, master, command, width=18):
        self.var = tk.StringVar()
        super().__init__(master, textvariable=self.var, compound="left", width=width,
                         style="Dropdown.TMenubutton")
        self.command = command  # καλείται με την τιμή που διάλεξε ο χρήστης
        self.items = []  # (τιμή, κείμενο, εικονίδιο)
        self.value = None
        self._popup = None
        self._closed_at = 0.0  # για να μην ξανανοίγει με το ίδιο κλικ που την έκλεισε
        self.bind("<Button-1>", self._toggle)
        self.bind("<Down>", self._toggle)

    def set_items(self, items):
        self.items = list(items)

    def set(self, value):
        for item_value, label, icon in self.items:
            if item_value == value:
                self.value = value
                self.var.set(label)
                self.configure(image=icon)
                return

    def _toggle(self, _event):
        if self._popup is not None:
            self._close()
        elif time.monotonic() - self._closed_at > 0.2:
            self._open()
        return "break"

    def _open(self):
        top = self._popup = tk.Toplevel(self)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        tree = ttk.Treeview(top, show="tree", selectmode="browse", height=len(self.items))
        tree.column("#0", width=max(self.winfo_width(), 180))
        for i, (value, label, icon) in enumerate(self.items):
            tree.insert("", "end", iid=str(i), text=f" {label}", image=icon)
            if value == self.value:
                tree.selection_set(str(i))
                tree.focus(str(i))
        tree.pack(fill="both", expand=True)
        top.geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height()}")
        tree.bind("<ButtonRelease-1>", lambda e: self._choose(tree.identify_row(e.y)))
        tree.bind("<Return>", lambda _: self._choose(tree.focus()))
        tree.bind("<Escape>", lambda _: self._close())
        if sys.platform == "win32":
            tree.bind("<FocusOut>", lambda _: self._close())
        else:
            # Στο X11 το κλικ έξω από τη λίστα δεν αλλάζει πάντα την εστίαση, οπότε
            # χρειάζεται grab, όπως κάνει και το Combobox για τη δική του λίστα.
            top.bind("<Button>", lambda e: self._close_if_outside(e, tree))
            top.wait_visibility()
            try:
                top.grab_set_global()
            except tk.TclError:  # το grab το κρατά άλλο πρόγραμμα
                top.grab_set()
        tree.focus_force()

    def _close_if_outside(self, event, tree):
        if self.winfo_containing(event.x_root, event.y_root) is not tree:
            self._close()

    def _close(self):
        if self._popup is not None:
            self._popup.destroy()
            self._popup = None
            self._closed_at = time.monotonic()

    def _choose(self, iid):
        if not iid:
            return
        value = self.items[int(iid)][0]
        self._close()
        self.set(value)
        self.command(value)


class CategoryDialog(tk.Toplevel):
    """Παράθυρο επιλογής κατηγορίας για μία ή περισσότερες κινήσεις."""

    def __init__(self, master, txs, categories, current, whole_description=False):
        super().__init__(master)
        self.title(t("dialog.title"))
        self.transient(master)
        self.resizable(False, False)
        self.result = None
        self.categories = categories

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        total = sum(tx.amount for tx in txs)
        descriptions = sorted({tx.description for tx in txs})
        summary = t("tx.summary", count=len(txs), total=fmt(total))
        if len(descriptions) == 1:
            summary = f"{descriptions[0]}\n{summary}"
        ttk.Label(body, text=summary, foreground=colors().text_muted).pack(anchor="w", pady=(0, 10))

        ttk.Label(body, text=t("dialog.prompt")).pack(anchor="w")
        self.name_var = tk.StringVar(value=current)
        box = ttk.Combobox(body, textvariable=self.name_var, values=categories, width=40)
        box.pack(fill="x", pady=(2, 10))
        box.focus_set()
        box.select_range(0, "end")

        self.whole_var = tk.BooleanVar(value=whole_description)
        ttk.Checkbutton(body, variable=self.whole_var, text=t("dialog.whole")).pack(anchor="w")

        self.income_var = tk.BooleanVar(value=all(tx.amount > 0 for tx in txs))
        self.income_check = ttk.Checkbutton(body, variable=self.income_var, text=t("dialog.income"))
        self.income_check.pack(anchor="w", pady=(4, 0))
        self.name_var.trace_add("write", lambda *_: self._toggle_income())
        self._toggle_income()

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text=t("dialog.cancel"), command=self.destroy).pack(side="right")
        ttk.Button(buttons, text=t("dialog.ok"), command=self._ok).pack(side="right", padx=6)
        self.bind("<Return>", lambda _: self._ok())
        self.bind("<Escape>", lambda _: self.destroy())

        run_modal(self)

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


class ImportDialog(tk.Toplevel):
    """Παράθυρο επιβεβαίωσης της τράπεζας κάθε αρχείου πριν από την εισαγωγή."""

    def __init__(self, master, files, banks):
        super().__init__(master)
        self.title(t("import.title"))
        self.transient(master)
        self.resizable(False, False)
        self.result = None
        self.banks = banks

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=t("import.prompt")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.rows = []  # (αρχείο, μεταβλητή τράπεζας)
        for i, (path, bank) in enumerate(files, start=1):
            ttk.Label(body, text=path.name).grid(row=i, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=bank_label(bank))
            ttk.Combobox(body, textvariable=var, values=[bank_label(b) for b in banks],
                         width=24).grid(row=i, column=1, sticky="e", padx=(12, 0), pady=2)
            self.rows.append((path, var))

        buttons = ttk.Frame(body)
        buttons.grid(row=len(files) + 1, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ttk.Button(buttons, text=t("dialog.cancel"), command=self.destroy).pack(side="right")
        ttk.Button(buttons, text=t("import.ok"), command=self._ok).pack(side="right", padx=6)
        self.bind("<Return>", lambda _: self._ok())
        self.bind("<Escape>", lambda _: self.destroy())

        run_modal(self)

    def _ok(self):
        result = [(path, bank_key(var.get(), self.banks)) for path, var in self.rows]
        if all(bank for _, bank in result):
            self.result = result
            self.destroy()


class ImportsDialog(tk.Toplevel):
    """Λίστα των εισαγωγών της βάσης, με δυνατότητα διαγραφής."""

    def __init__(self, master, db_file: Path):
        super().__init__(master)
        self.title(t("imports.title"))
        self.transient(master)
        self.geometry("880x360")
        self.db_file = db_file
        self.changed = False

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        buttons = ttk.Frame(body)
        buttons.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(buttons, text=t("imports.close"), command=self.destroy).pack(side="right")
        ttk.Button(buttons, text=t("imports.delete"), command=self._delete).pack(side="left")
        frame, self.tree = make_tree(
            body, ["col.file", "col.bank", "col.period", "col.imported_at", "col.transactions"],
            [280, 140, 170, 120, 80], anchors={4: "e"},
        )
        frame.pack(fill="both", expand=True)
        self.bind("<Escape>", lambda _: self.destroy())
        self._fill()

        run_modal(self)

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        for record in database.list_imports(self.db_file):
            period = (f"{record.first_date:%d/%m/%Y} – {record.last_date:%d/%m/%Y}"
                      if record.first_date else "-")
            self.tree.insert("", "end", iid=str(record.id), values=(
                record.file_name, bank_label(record.bank), period,
                f"{record.imported_at:%d/%m/%Y %H:%M}", record.rows))

    def _delete(self):
        selection = self.tree.selection()
        if not selection:
            return
        names = "\n".join(self.tree.item(iid, "values")[0] for iid in selection)
        if not messagebox.askyesno(t("imports.title"), t("imports.confirm", files=names), parent=self):
            return
        for iid in selection:
            database.delete_import(self.db_file, int(iid))
        self.changed = True
        self._fill()


class CategoriesDialog(tk.Toplevel):
    """Διαχείριση κατηγοριών: σειρά, όνομα, έσοδο/έξοδο και λέξεις-κλειδιά.

    Οι αλλαγές της φόρμας αποθηκεύονται όταν ο χρήστης φεύγει από την κατηγορία
    ή κλείνει το παράθυρο."""

    def __init__(self, master, db_file: Path):
        super().__init__(master)
        self.title(t("categories.title"))
        self.transient(master)
        self.geometry("760x500")
        self.minsize(640, 400)
        self.db_file = db_file
        self.changed = False
        self.records: dict[int, database.CategoryRecord] = {}
        self.current: int | None = None  # η κατηγορία που δείχνει η φόρμα

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        footer = ttk.Frame(body)
        footer.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(footer, text=t("categories.close"), command=self._close).pack(side="right")
        ttk.Label(footer, text=t("categories.hint"), foreground=colors().text_muted,
                  wraplength=580, justify="left").pack(side="left")

        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        buttons = ttk.Frame(left)
        buttons.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(buttons, text=t("categories.add"), command=self._add).pack(side="left")
        self.delete_button = ttk.Button(buttons, text=t("categories.delete"), command=self._delete)
        self.delete_button.pack(side="left", padx=6)
        ttk.Button(buttons, text=t("categories.down"), width=3, command=lambda: self._move(1)).pack(side="right")
        ttk.Button(buttons, text=t("categories.up"), width=3,
                   command=lambda: self._move(-1)).pack(side="right", padx=6)
        frame, self.tree = make_tree(left, ["col.category", "col.keywords"], [220, 70], anchors={1: "e"})
        self.tree.configure(selectmode="browse")
        frame.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        form = ttk.Frame(body)
        form.pack(side="left", fill="both", expand=True, padx=(16, 0))
        ttk.Label(form, text=t("categories.name")).pack(anchor="w")
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(form, textvariable=self.name_var)
        self.name_entry.pack(fill="x", pady=(2, 8))
        self.income_var = tk.BooleanVar()
        self.income_check = ttk.Checkbutton(form, variable=self.income_var, text=t("categories.income"))
        self.income_check.pack(anchor="w", pady=(0, 8))
        ttk.Label(form, text=t("categories.keywords")).pack(anchor="w")
        text_frame = ttk.Frame(form)
        text_frame.pack(fill="both", expand=True, pady=(2, 0))
        # Το Text δεν είναι widget ttk, οπότε παίρνει τα χρώματα του θέματος απευθείας.
        self.keywords_text = tk.Text(
            text_frame, width=30, height=10, wrap="none", font=theme.font(9), relief="solid", borderwidth=1,
            bg=colors().field, fg=colors().text, insertbackground=colors().text,
            selectbackground=colors().select, selectforeground=colors().select_text,
            highlightthickness=0,
        )
        scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.keywords_text.yview)
        self.keywords_text.configure(yscrollcommand=scroll.set)
        self.keywords_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.bind("<Escape>", lambda _: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._fill()
        children = self.tree.get_children()
        if children:
            self._show(int(children[0]))
            self.tree.selection_set(children[0])

        run_modal(self)

    def _fill(self):
        """Ξαναγεμίζει τη λίστα από τη βάση, κρατώντας την επιλογή."""
        self.records = {record.id: record for record in database.load_categories(self.db_file)}
        self.tree.delete(*self.tree.get_children())
        for record in self.records.values():
            self.tree.insert("", "end", iid=str(record.id), values=(record.name, len(record.keywords)),
                             tags=("income",) if record.is_income else ())
        if self.current in self.records:
            self.tree.selection_set(str(self.current))
            self.tree.see(str(self.current))

    def _on_select(self, _event):
        selection = self.tree.selection()
        selected = int(selection[0]) if selection else None
        if selected == self.current:
            return
        if not self._save_form():
            self.tree.selection_set(str(self.current))  # μένει στην κατηγορία με το σφάλμα
            return
        self._show(selected)
        if selected is not None:  # το _fill της αποθήκευσης ξαναδιάλεξε την προηγούμενη
            self.tree.selection_set(str(selected))

    def _show(self, category_id: int | None):
        self.current = category_id
        record = self.records.get(category_id)
        self.name_var.set(record.name if record else "")
        self.income_var.set(record.is_income if record else False)
        self.keywords_text.delete("1.0", "end")
        if record:
            self.keywords_text.insert("1.0", "\n".join(record.keywords))
        editable = ["!disabled"] if record and not record.is_system else ["disabled"]
        self.name_entry.state(editable)
        self.income_check.state(editable)
        self.delete_button.state(editable)

    def _form_keywords(self) -> list[str]:
        # Χωρίς strip: τα κενά στις λέξεις-κλειδιά μετράνε στο ταίριασμα.
        return [line for line in self.keywords_text.get("1.0", "end-1c").split("\n") if line.strip()]

    def _save_form(self) -> bool:
        """Αποθηκεύει ό,τι άλλαξε στη φόρμα· False αν απέτυχε (π.χ. όνομα που υπάρχει ήδη)."""
        record = self.records.get(self.current)
        if record is None:
            return True
        name, keywords = self.name_var.get().strip(), self._form_keywords()
        is_income = self.income_var.get()
        if name == record.name and is_income == record.is_income and keywords == record.keywords:
            return True
        try:
            if name != record.name:
                database.rename_category(self.db_file, record.id, name)
            if is_income != record.is_income:
                database.set_category_income(self.db_file, record.id, is_income)
            if keywords != record.keywords:
                database.set_keywords(self.db_file, record.id, keywords)
        except ValueError as exc:
            messagebox.showerror(t("msg.error"), str(exc), parent=self)
            return False
        self.changed = True
        self._fill()
        return True

    def _add(self):
        if not self._save_form():
            return
        base = t("categories.new_name")
        names = {record.name for record in self.records.values()}
        name, number = base, 1
        while name in names:
            number += 1
            name = f"{base} {number}"
        new_id = database.add_category(self.db_file, name)
        self.changed = True
        self._fill()
        self._show(new_id)
        self.tree.selection_set(str(new_id))
        self.tree.see(str(new_id))
        self.name_entry.focus_set()
        self.name_entry.select_range(0, "end")

    def _delete(self):
        record = self.records.get(self.current)
        if record is None or record.is_system:
            return
        if not messagebox.askyesno(t("categories.title"), t("categories.confirm", name=record.name), parent=self):
            return
        database.delete_category(self.db_file, record.id)
        self.changed = True
        children = self.tree.get_children()
        index = children.index(str(record.id))
        neighbour = children[index + 1] if index + 1 < len(children) else children[index - 1] if index else None
        self.current = None  # για να μην ξαναγραφτεί η φόρμα στην κατηγορία που διαγράφηκε
        self._fill()
        self._show(int(neighbour) if neighbour else None)
        if neighbour:
            self.tree.selection_set(neighbour)

    def _move(self, step: int):
        if self.current is None or not self._save_form():
            return
        database.move_category(self.db_file, self.current, step)
        self.changed = True
        self._fill()

    def _close(self):
        if self._save_form():
            self.destroy()


class MyMoneyApp(tk.Tk):
    def __init__(self, db_file: Path, settings_file: Path | None = None):
        super().__init__()
        self.db_file = db_file
        self.settings_file = settings_file
        self.tx_items = {}  # iid του πίνακα κινήσεων -> Transaction
        self.geometry("1150x780")
        self.minsize(900, 640)
        theme.apply(self)

        self.all_transactions = []
        self.imports: list[database.ImportRecord] = []
        self.banks: list[str] = []  # ονόματα τραπεζών, ταξινομημένα κατά εμφανιζόμενο όνομα
        self._months: list[str] = []  # μήνες («01».. «12») του φίλτρου μήνα
        self.stats: Stats | None = None
        self.bank_stats: dict[str, Stats] = {}
        self.transfers = []  # μεταφορές μεταξύ τραπεζών της τρέχουσας περιόδου
        self._bank: str | None = None  # επιλεγμένη τράπεζα ή None για όλες
        self._bank_icons: dict[str, tk.PhotoImage] = {}

        self._build_ui()
        self.reload()

    # ---------- κατασκευή UI ----------

    def _build_ui(self):
        """Χτίζει όλο το παράθυρο στην τρέχουσα γλώσσα (ξανά, όταν αλλάζει)."""
        for child in self.winfo_children():
            child.destroy()
        self.title(t("app.title"))
        self._build_toolbar()
        self._build_cards()
        self._build_statusbar()
        self._build_tabs()

    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=(12, 10))
        bar.pack(fill="x")
        # Γλώσσα και θέμα πρώτα, ώστε να μην κρύβονται όταν το παράθυρο στενεύει.
        self.language_var = tk.StringVar(value=i18n.LANGUAGES[i18n.get_language()])
        language_box = ttk.Combobox(bar, textvariable=self.language_var, state="readonly", width=9,
                                    values=list(i18n.LANGUAGES.values()))
        language_box.pack(side="right")
        language_box.bind("<<ComboboxSelected>>", lambda _: self._on_language())
        ttk.Button(bar, command=self._toggle_theme,
                   text=t("theme.to_light" if theme.get_theme() == "dark" else "theme.to_dark"),
                   ).pack(side="right", padx=(12, 6))

        ttk.Label(bar, text=t("toolbar.year")).pack(side="left")
        self.year_var = tk.StringVar(value=t("all_years"))
        self.year_box = ttk.Combobox(bar, textvariable=self.year_var, state="readonly", width=12)
        self.year_box.pack(side="left", padx=(6, 16))
        self.year_box.bind("<<ComboboxSelected>>", lambda _: self._on_year())

        ttk.Label(bar, text=t("toolbar.month")).pack(side="left")
        self.month_var = tk.StringVar(value=t("all_months"))
        self.month_box = ttk.Combobox(bar, textvariable=self.month_var, state="readonly", width=14)
        self.month_box.pack(side="left", padx=(6, 16))
        self.month_box.bind("<<ComboboxSelected>>", lambda _: self.refresh())

        ttk.Label(bar, text=t("toolbar.bank")).pack(side="left")
        self.bank_box = IconDropdown(bar, command=self._select_bank, width=16)
        self.bank_box.pack(side="left", padx=(6, 16))

        # Οι ενέργειες σε δική τους γραμμή, ώστε να χωράνε και στο ελάχιστο πλάτος.
        actions = ttk.Frame(self, padding=(12, 0, 12, 10))
        actions.pack(fill="x")
        ttk.Button(actions, text=t("toolbar.import"), command=self._import_files).pack(side="left")
        ttk.Button(actions, text=t("toolbar.imports"), command=self._open_imports).pack(side="left", padx=6)
        ttk.Button(actions, text=t("toolbar.reload"), command=self.reload).pack(side="left")
        ttk.Button(actions, text=t("toolbar.categories"), command=self._open_categories).pack(side="left", padx=6)

    def _build_statusbar(self):
        bar = ttk.Frame(self, padding=(12, 0, 12, 10))
        bar.pack(side="bottom", fill="x")
        self.status_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.status_var, foreground=colors().text_muted).pack(side="left")

    def _build_cards(self):
        row = ttk.Frame(self, padding=(12, 0, 12, 8))
        row.pack(fill="x")
        self.card_vars = {}
        keys = ["card.income", "card.expenses", "card.net", "card.balance", "card.avg_daily", "card.count"]
        for i, key in enumerate(keys):
            card = ttk.Frame(row, style="Card.TFrame", padding=(12, 8))
            card.grid(row=0, column=i, sticky="nsew", padx=4)
            row.columnconfigure(i, weight=1)
            ttk.Label(card, text=t(key), style="CardTitle.TLabel").pack(anchor="w")
            var = tk.StringVar(value="-")
            ttk.Label(card, textvariable=var, style="CardValue.TLabel").pack(anchor="w")
            self.card_vars[key] = var

    def _build_tabs(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.notebook = nb

        # Ανά έτος
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text=t("tab.years"))
        self.year_chart = ChartPanel(tab, height=3.6)
        self.year_chart.pack(fill="both", expand=True)
        frame, self.year_tree = make_tree(
            tab, ["col.year", "col.income", "col.expenses", "col.net", "col.avg_monthly",
                  "col.months", "col.transactions"],
            [100, 140, 140, 140, 150, 70, 90], anchors={i: "e" for i in range(1, 7)},
        )
        frame.configure(height=150)
        frame.pack_propagate(False)
        frame.pack(fill="x", pady=(8, 0))

        # Ανά μήνα
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text=t("tab.months"))
        self.month_chart = ChartPanel(tab, height=3.6)
        self.month_chart.pack(fill="both", expand=True)
        frame, self.month_tree = make_tree(
            tab, ["col.month", "col.income", "col.expenses", "col.net"], [150, 150, 150, 150],
            anchors={1: "e", 2: "e", 3: "e"},
        )
        frame.configure(height=170)
        frame.pack_propagate(False)
        frame.pack(fill="x", pady=(8, 0))

        # Ανά τράπεζα
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text=t("tab.banks"))
        self.bank_chart = ChartPanel(tab, height=3.4)
        self.bank_chart.pack(fill="both", expand=True)
        frame, self.bank_tree = make_tree(
            tab, ["col.bank", "col.income", "col.expenses", "col.net", "col.balance", "col.transactions"],
            [180, 130, 130, 130, 130, 80], anchors={1: "e", 2: "e", 3: "e", 4: "e", 5: "e"},
        )
        frame.configure(height=150)
        frame.pack_propagate(False)
        frame.pack(fill="x", pady=(8, 0))
        self.bank_tree.bind("<Double-1>", self._on_bank_open)
        self.transfer_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.transfer_var, foreground=colors().text_muted,
                  wraplength=1000, justify="left").pack(anchor="w", pady=(4, 0))

        # Κατηγορίες εξόδων
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text=t("tab.categories"))
        paned = ttk.PanedWindow(tab, orient="horizontal")
        paned.pack(fill="both", expand=True)
        self.cat_chart = ChartPanel(paned)
        frame, self.cat_tree = make_tree(
            paned, ["col.category", "col.amount", "%", "col.count"], [160, 95, 55, 55],
            anchors={1: "e", 2: "e", 3: "e"},
        )
        self.cat_tree.bind("<Double-1>", self._on_category_open)
        paned.add(self.cat_chart, weight=3)
        paned.add(frame, weight=2)
        ttk.Label(tab, text=t("hint.categories"), foreground=colors().text_muted).pack(anchor="w", pady=(4, 0))

        # Ημερήσια έξοδα
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text=t("tab.daily"))
        self.daily_chart = ChartPanel(tab)
        self.daily_chart.pack(fill="both", expand=True)

        # Top δαπάνες ανά έμπορο
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text=t("tab.merchants"))
        frame, self.merchant_tree = make_tree(
            tab, ["col.description", "col.category", "col.total", "col.count", "col.average"],
            [320, 200, 120, 70, 120], anchors={2: "e", 3: "e", 4: "e"},
        )
        frame.pack(fill="both", expand=True)
        self.merchant_tree.bind("<Double-1>", self._on_merchant_edit)
        ttk.Label(tab, text=t("hint.merchants"), foreground=colors().text_muted).pack(anchor="w", pady=(4, 0))

        # Κινήσεις
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text=t("tab.transactions"))
        self.tx_tab = tab
        filters = ttk.Frame(tab)
        filters.pack(fill="x", pady=(0, 6))
        ttk.Label(filters, text=t("tx.search")).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._fill_transactions())
        ttk.Entry(filters, textvariable=self.search_var, width=30).pack(side="left", padx=6)
        ttk.Label(filters, text=t("tx.category")).pack(side="left", padx=(12, 0))
        self.cat_filter_var = tk.StringVar(value=t("all_categories"))
        self.cat_filter_box = ttk.Combobox(filters, textvariable=self.cat_filter_var, state="readonly", width=28)
        self.cat_filter_box.pack(side="left", padx=6)
        self.cat_filter_box.bind("<<ComboboxSelected>>", lambda _: self._fill_transactions())
        self.tx_total_var = tk.StringVar()
        ttk.Label(filters, textvariable=self.tx_total_var, foreground=colors().text_muted).pack(side="right")
        frame, self.tx_tree = make_tree(
            tab, ["col.date", "col.bank", "col.description", "col.category", "col.amount", "col.balance"],
            [100, 120, 320, 190, 110, 120], anchors={4: "e", 5: "e"},
        )
        frame.pack(fill="both", expand=True)

        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text=t("tx.change_category"), command=self._edit_selected).pack(side="left")
        ttk.Button(actions, text=t("tx.reset_category"),
                   command=self._clear_selected).pack(side="left", padx=6)
        ttk.Label(actions, foreground=colors().text_muted, text=t("hint.transactions")).pack(side="left", padx=12)

        self.tx_menu = tk.Menu(self, tearoff=False)
        self.tx_menu.add_command(label=t("tx.change_category"), command=self._edit_selected)
        self.tx_menu.add_command(label=t("tx.reset_category"), command=self._clear_selected)
        self.tx_tree.bind("<Double-1>", lambda _: self._edit_selected())
        self.tx_tree.bind("<Button-3>", self._on_tx_right_click)
        self.tx_tree.bind("<Control-KeyPress>", self._on_tx_ctrl_key)

    # ---------- γλώσσα και θέμα ----------

    def _on_language(self):
        codes = {name: code for code, name in i18n.LANGUAGES.items()}
        language = codes[self.language_var.get()]
        if language == i18n.get_language():
            return
        self._rebuild(lambda: i18n.set_language(language))
        if self.settings_file is not None:
            i18n.save_settings(self.settings_file)

    def _toggle_theme(self):
        name = "light" if theme.get_theme() == "dark" else "dark"
        self._rebuild(lambda: (theme.set_theme(name), theme.apply(self)))
        if self.settings_file is not None:
            theme.save_settings(self.settings_file)

    def _rebuild(self, change):
        """Ξαναχτίζει το παράθυρο μετά το change(), κρατώντας φίλτρα και καρτέλα."""
        # Κρατάμε τις επιλογές φίλτρων σε μορφή ανεξάρτητη από τη γλώσσα.
        year, month = self._selected_year(), self._selected_month()
        bank = self._selected_bank()
        tab = self.notebook.index(self.notebook.select())
        change()
        self._build_ui()
        self._update_filters(year, month, bank)
        self.refresh()
        self.notebook.select(tab)

    # ---------- δεδομένα ----------

    def _selected_year(self) -> str | None:
        """π.χ. «2026», ή None για όλα τα έτη."""
        year = self.year_var.get()
        return None if year == t("all_years") else year

    def _selected_month(self) -> str | None:
        """Αριθμός μήνα π.χ. «09», ή None για όλους τους μήνες."""
        names = {month_name(m): m for m in self._months}
        return names.get(self.month_var.get())

    def _on_year(self):
        self._update_months(self._selected_month())
        self.refresh()

    def _update_months(self, month: str | None):
        """Μήνες με κινήσεις στο επιλεγμένο έτος (ή σε οποιοδήποτε έτος)."""
        year = self._selected_year()
        self._months = sorted({tx.date.strftime("%m") for tx in self.all_transactions
                               if tx.in_period(year)})
        self.month_box["values"] = [t("all_months"), *map(month_name, self._months)]
        self.month_var.set(month_name(month) if month in self._months else t("all_months"))

    def _selected_bank(self) -> str | None:
        return self._bank

    def _select_bank(self, bank: str | None):
        self._bank = bank
        self.bank_box.set(bank)
        self.refresh()

    def _bank_icon(self, bank: str | None) -> tk.PhotoImage:
        """Λογότυπο της τράπεζας, ή κενό εικονίδιο ίδιου μεγέθους ώστε να στοιχίζονται τα ονόματα."""
        key = bank.casefold() if bank else ""
        if key not in self._bank_icons:
            path = BANK_LOGOS / f"{key}.png"
            try:
                icon = tk.PhotoImage(master=self, file=path) if key and path.exists() else None
            except tk.TclError:  # χαλασμένο αρχείο εικόνας
                icon = None
            self._bank_icons[key] = icon or tk.PhotoImage(master=self, width=20, height=20)
        return self._bank_icons[key]

    def reload(self):
        year, month, bank = self._selected_year(), self._selected_month(), self._selected_bank()
        try:
            self.all_transactions = database.load_transactions(self.db_file)
            self.imports = database.list_imports(self.db_file)
            self.categorizer = Categorizer.from_db(self.db_file)
        except Exception as exc:  # εμφάνιση σφάλματος αντί για crash
            messagebox.showerror(t("msg.error"), t("msg.load_failed", error=exc))
            return
        self.banks = sorted({tx.bank for tx in self.all_transactions}, key=bank_label)
        self._update_filters(year, month, bank)
        self.refresh()

    def _update_filters(self, year: str | None, month: str | None, bank: str | None):
        self.status_var.set(t("status", banks=len(self.banks), files=len(self.imports),
                              count=len(self.all_transactions))
                            if self.all_transactions else t("status.empty"))
        years = sorted({tx.year for tx in self.all_transactions}, reverse=True)
        self.year_box["values"] = [t("all_years"), *years]
        self.year_var.set(year if year in years else t("all_years"))
        self._update_months(month)
        self.bank_box.set_items((b, bank_label(b) if b else t("all_banks"), self._bank_icon(b))
                                for b in [None, *self.banks])
        self._bank = bank if bank in self.banks else None
        self.bank_box.set(self._bank)

    def refresh(self):
        year, month = self._selected_year(), self._selected_month()
        txs = [tx for tx in self.all_transactions if tx.in_period(year, month)]
        # Κάθε τράπεζα ξεχωριστά: οι μεταφορές προς/από άλλες τράπεζες μετράνε κανονικά.
        self.bank_stats = {
            bank: compute([tx for tx in txs if tx.bank == bank], self.categorizer)
            for bank in self.banks
        }
        # Σύνολο: οι μεταφορές μεταξύ των τραπεζών αλληλοαναιρούνται.
        combined, self.transfers = split_transfers(txs)
        self.combined_stats = compute(combined, self.categorizer)
        bank = self._selected_bank()
        self.stats = self.combined_stats if bank is None else self.bank_stats[bank]
        self._fill_cards()
        self._fill_years()
        self._fill_months()
        self._fill_banks()
        self._fill_categories()
        self._fill_daily()
        self._fill_merchants()
        cats = sorted(set(self.stats.categories.values()))
        self.cat_filter_box["values"] = [t("all_categories"), *cats]
        if self.cat_filter_var.get() not in self.cat_filter_box["values"]:
            self.cat_filter_var.set(t("all_categories"))
        self._fill_transactions()

    def _fill_cards(self):
        s = self.stats
        self.card_vars["card.income"].set(fmt(s.income))
        self.card_vars["card.expenses"].set(fmt(s.expenses))
        self.card_vars["card.net"].set(("+" if s.net > 0 else "") + fmt(s.net))
        self.card_vars["card.balance"].set(fmt(s.last_balance))
        self.card_vars["card.avg_daily"].set(fmt(s.avg_daily_expense))
        self.card_vars["card.count"].set(str(len(s.transactions)))

    def _income_expense_chart(self, chart, rows, title):
        """Ομαδοποιημένες μπάρες εσόδων/εξόδων· rows = [(ετικέτα, έσοδα, έξοδα)]."""
        ax = chart.new_axes()
        if rows:
            labels = [label for label, _, _ in rows]
            x = range(len(labels))
            w = 0.38
            inc = ax.bar([i - w / 2 - 0.01 for i in x], [float(r[1]) for r in rows],
                         width=w, color=colors().income, label=t("col.income"))
            exp = ax.bar([i + w / 2 + 0.01 for i in x], [float(r[2]) for r in rows],
                         width=w, color=colors().expense, label=t("col.expenses"))
            for (label, income, _), b in zip(rows, inc):
                chart.add_hover(b, f"{label}\n{t('hover.income', amount=fmt(income))}")
            for (label, _, expenses), b in zip(rows, exp):
                chart.add_hover(b, f"{label}\n{t('hover.expenses', amount=fmt(expenses))}")
            ax.set_xticks(list(x), labels)
            ax.set_xlim(-0.6, max(len(labels) - 0.4, 1.4))
            _euro_formatter(ax)
            top = max(max(r[1], r[2]) for r in rows)
            ax.set_ylim(0, float(top) * 1.2 or 1)
            ax.legend(frameon=False, loc="upper right", ncols=2, fontsize=9, labelcolor=colors().text_muted)
            ax.set_title(title, loc="left", fontsize=11, color=colors().text)
        chart.draw()

    def _fill_years(self):
        s = self.stats
        tree = self.year_tree
        tree.delete(*tree.get_children())
        for y in reversed(s.years):
            tree.insert("", "end", values=(y.year, fmt(y.income), fmt(y.expenses), fmt(y.net),
                                           fmt(y.avg_monthly_expense), len(y.months), y.count))
        if len(s.years) > 1:
            tree.insert("", "end", values=(t("total"), fmt(s.income), fmt(s.expenses), fmt(s.net),
                                           "", len(s.months), len(s.transactions)), tags=("total",))
        self._income_expense_chart(self.year_chart, [(y.year, y.income, y.expenses) for y in s.years],
                                   t("chart.years"))

    def _fill_months(self):
        s = self.stats
        tree = self.month_tree
        tree.delete(*tree.get_children())
        for m in reversed(s.months):
            tree.insert("", "end", values=(m.month, fmt(m.income), fmt(m.expenses), fmt(m.net)))
        if len(s.months) > 1:
            tree.insert("", "end", values=(t("total"), fmt(s.income), fmt(s.expenses), fmt(s.net)),
                        tags=("total",))
        self._income_expense_chart(self.month_chart, [(m.month, m.income, m.expenses) for m in s.months],
                                   t("chart.months"))

    def _fill_banks(self):
        tree = self.bank_tree
        tree.delete(*tree.get_children())
        rows = [(bank, s) for bank, s in self.bank_stats.items() if s.transactions]
        for bank, s in rows:
            tree.insert("", "end", values=(bank_label(bank), fmt(s.income), fmt(s.expenses), fmt(s.net),
                                           fmt(s.last_balance), len(s.transactions)))
        if len(rows) > 1:
            total = self.combined_stats
            tree.insert("", "end", values=(t("total"), fmt(total.income), fmt(total.expenses),
                                           fmt(total.net), fmt(total.last_balance),
                                           len(total.transactions)), tags=("total",))

        hint = t("hint.bank_open")
        if self.transfers:
            moved = sum(tx.amount for tx in self.transfers if tx.amount > 0)
            hint = t("hint.transfers", count=len(self.transfers) // 2, amount=fmt(moved)) + hint
        self.transfer_var.set(hint)

        self._income_expense_chart(self.bank_chart,
                                   [(bank_label(bank), s.income, s.expenses) for bank, s in rows],
                                   t("chart.banks"))

    def _on_bank_open(self, _event):
        sel = self.bank_tree.selection()
        if not sel:
            return
        name = self.bank_tree.item(sel[0], "values")[0]
        banks = {bank_label(b): b for b in self.banks}
        self._select_bank(banks.get(name))

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
        ax.grid(axis="x", color=colors().grid, linewidth=0.8)
        cats = list(reversed(s.expense_categories))
        if cats:
            bars = ax.barh([c.name for c in cats], [float(c.total) for c in cats],
                           color=colors().expense, height=0.6)
            for c, b in zip(cats, bars):
                pct = c.total / s.expenses * 100
                chart.add_hover(b, f"{c.name}\n" + t("hover.category", amount=fmt(c.total),
                                                      pct=f"{pct:.1f}", count=c.count))
                ax.text(b.get_width(), b.get_y() + b.get_height() / 2, f"  {fmt(c.total)}",
                        va="center", fontsize=8, color=colors().text_muted)
            ax.set_xlim(0, max(float(cats[-1].total), 1) * 1.25)
            _euro_formatter(ax, "x")
            ax.set_title(t("chart.categories"), loc="left", fontsize=11, color=colors().text)
        chart.draw()

    def _fill_daily(self):
        chart = self.daily_chart
        ax = chart.new_axes()
        daily = self.stats.daily_expenses
        if daily:
            days = list(daily)
            bars = ax.bar(days, [float(v) for v in daily.values()], color=colors().expense, width=0.7)
            for d, b in zip(days, bars):
                chart.add_hover(b, f"{d:%d/%m/%Y}\n{fmt(daily[d])}")
            avg = float(self.stats.avg_daily_expense)
            ax.axhline(avg, color=colors().text_muted, linewidth=1, linestyle="--")
            ax.text(days[0], avg, t("chart.average", amount=fmt(self.stats.avg_daily_expense)),
                    va="bottom", fontsize=8, color=colors().text_muted)
            ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d/%m"))
            _euro_formatter(ax)
            ax.set_title(t("chart.daily"), loc="left", fontsize=11, color=colors().text)
        chart.draw()

    def _fill_merchants(self):
        s = self.stats
        tree = self.merchant_tree
        tree.delete(*tree.get_children())
        cat_of = {tx.description: s.categories[tx] for tx in s.transactions}
        for m in s.top_merchants:
            tree.insert("", "end", values=(m.name, cat_of.get(m.name, ""), fmt(m.total),
                                           m.count, fmt(m.total / m.count)))

    def _fill_transactions(self):
        if self.stats is None:
            return
        query = self.search_var.get().casefold().strip()
        cat = self.cat_filter_var.get()
        all_categories = t("all_categories")
        tree = self.tx_tree
        tree.delete(*tree.get_children())
        self.tx_items = {}
        total = 0
        count = 0
        for tx in reversed(self.stats.transactions):
            tcat = self.stats.categories[tx]
            if cat != all_categories and tcat != cat:
                continue
            if query and query not in tx.description.casefold():
                continue
            total += tx.amount
            count += 1
            shown_cat = f"✎ {tcat}" if self.categorizer.is_manual(tx) else tcat
            iid = tree.insert("", "end", values=(f"{tx.date:%d/%m/%Y}", bank_label(tx.bank), tx.description,
                                                 shown_cat, fmt(tx.amount), fmt(tx.balance)),
                              tags=("income" if tx.is_income else "expense",))
            self.tx_items[iid] = tx
        self.tx_total_var.set(t("tx.summary", count=count, total=fmt(total)))

    # ---------- χειροκίνητες κατηγορίες ----------

    def _selected_transactions(self):
        return [self.tx_items[iid] for iid in self.tx_tree.selection() if iid in self.tx_items]

    def _on_tx_ctrl_key(self, event):
        """Ctrl+A: όλες οι κινήσεις που φαίνονται. Στα Windows ο κωδικός 65 είναι το φυσικό
        πλήκτρο A, οπότε δουλεύει και με ελληνικό πληκτρολόγιο, όπου το ίδιο πλήκτρο δίνει α.
        Στο Linux το α φτάνει ως δικό του keysym."""
        if (event.keysym in ("a", "A", "Greek_alpha", "Greek_ALPHA")
                or (sys.platform == "win32" and event.keycode == 65)):
            self.tx_tree.selection_set(self.tx_tree.get_children())
            return "break"

    def _on_tx_right_click(self, event):
        row = self.tx_tree.identify_row(event.y)
        if row and row not in self.tx_tree.selection():
            self.tx_tree.selection_set(row)
        if self.tx_tree.selection():
            self.tx_menu.tk_popup(event.x_root, event.y_root)

    def _assign_dialog(self, txs, whole_description=False):
        if not txs:
            messagebox.showinfo(t("msg.category"), t("msg.select_first"))
            return
        current = {self.stats.categories[tx] for tx in txs}
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
        txs = [tx for tx in self.stats.transactions if tx.description == description]
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

    def _import_files(self):
        suffixes = list(SUPPORTED_SUFFIXES)
        if sys.platform != "win32":  # εκτός Windows το .CSV δεν ταιριάζει με το *.csv
            suffixes += [suffix.upper() for suffix in suffixes]
        patterns = " ".join(f"*{suffix}" for suffix in suffixes)
        names = filedialog.askopenfilenames(parent=self, title=t("import.title"),
                                            filetypes=[(t("import.filetype"), patterns)])
        if not names:
            return
        files, errors = [], []
        for path in map(Path, names):
            try:
                files.append((path, detect_bank(path)))
            except Exception as exc:  # χαλασμένο αρχείο ή άγνωστη μορφή
                errors.append(f"{path.name}: {exc}")
        results = []
        if files:
            banks = sorted({*known_banks(), *self.banks}, key=bank_label)
            dialog = ImportDialog(self, files, banks)
            if dialog.result is None:
                return
            for path, bank in dialog.result:
                try:
                    r = database.import_file(self.db_file, path, bank)
                except Exception as exc:
                    errors.append(f"{path.name}: {exc}")
                else:
                    results.append(t("import.result", file=r.file_name, bank=bank_label(r.bank),
                                     added=r.added, rows=r.rows))
            self.reload()
        message = "\n".join([*results, *errors])
        if errors:
            messagebox.showwarning(t("import.title"), message)
        else:
            messagebox.showinfo(t("import.title"), message)

    def _open_imports(self):
        if ImportsDialog(self, self.db_file).changed:
            self.reload()

    def _open_categories(self):
        if CategoriesDialog(self, self.db_file).changed:
            self.reload()
