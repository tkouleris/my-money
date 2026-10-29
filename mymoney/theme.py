"""Φωτεινό / σκοτεινό θέμα: χρώματα και στυλ ttk.

Το θέμα αποθηκεύεται στο settings.json· προεπιλογή το φωτεινό.
"""

import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from . import settings


@dataclass(frozen=True)
class Palette:
    surface: str  # φόντο παραθύρου και γραφημάτων
    card: str  # κάρτες, tooltip, επικεφαλίδες
    field: str  # πεδία, πίνακες, λίστες
    border: str
    hover: str
    select: str
    select_text: str
    text: str
    text_muted: str
    grid: str
    income: str  # σειρά 1
    expense: str  # σειρά 2


THEMES = {
    "light": Palette(
        surface="#fcfcfb", card="#ffffff", field="#ffffff", border="#d6d5d1", hover="#ecebe8",
        select="#0078d7", select_text="#ffffff", text="#0b0b0b", text_muted="#52514e",
        grid="#e4e3df", income="#2a78d6", expense="#eb6834",
    ),
    "dark": Palette(
        surface="#1e1f22", card="#2b2d31", field="#26282c", border="#3c3e43", hover="#35373c",
        select="#2f5d8f", select_text="#ffffff", text="#ececea", text_muted="#a3a29e",
        grid="#36383d", income="#5a9be6", expense="#f07f4f",
    ),
}
DEFAULT_THEME = "light"

_theme = DEFAULT_THEME


def get_theme() -> str:
    return _theme


def set_theme(name: str):
    global _theme
    _theme = name if name in THEMES else DEFAULT_THEME


def palette() -> Palette:
    return THEMES[_theme]


def load_settings(path: Path):
    set_theme(settings.read(path).get("theme", DEFAULT_THEME))


def save_settings(path: Path):
    settings.update(path, theme=_theme)


def apply(root: tk.Tk):
    """Εφαρμόζει το τρέχον θέμα στα στυλ ttk (πριν χτιστούν τα widgets)."""
    p = palette()
    style = ttk.Style(root)
    if _theme == "light" and "vista" in style.theme_names():
        style.theme_use("vista")  # εγγενής εμφάνιση των Windows
        # Λίστα με εικονίδια (IconDropdown) που μοιάζει με Combobox.
        style.layout("Dropdown.TMenubutton", [("Combobox.border", {"sticky": "nswe", "children": [
            ("Combobox.rightdownarrow", {"side": "right", "sticky": "ns"}),
            ("Combobox.padding", {"sticky": "nswe", "children": [
                ("Menubutton.label", {"side": "left", "sticky": "w"})]})]})])
        style.configure("Dropdown.TMenubutton", padding=(3, 1))
    else:
        # Το vista δεν δέχεται δικά του χρώματα, οπότε το σκοτεινό θέμα χτίζεται πάνω στο clam.
        style.theme_use("clam")
        style.configure(".", background=p.surface, foreground=p.text, fieldbackground=p.field,
                        bordercolor=p.border, lightcolor=p.surface, darkcolor=p.surface,
                        troughcolor=p.surface, selectbackground=p.select,
                        selectforeground=p.select_text, insertcolor=p.text, arrowcolor=p.text)
        style.map(".", background=[("disabled", p.surface), ("active", p.hover)],
                  foreground=[("disabled", p.text_muted)])
        style.configure("TButton", background=p.card, padding=(8, 3))
        style.map("TButton", background=[("pressed", p.border), ("active", p.hover)])
        style.map("TCombobox", fieldbackground=[("readonly", p.field)],
                  selectbackground=[("readonly", p.field)], selectforeground=[("readonly", p.text)])
        style.configure("TMenubutton", background=p.field, padding=(4, 1))
        style.configure("TCheckbutton", indicatorbackground=p.field, indicatorforeground=p.text)
        style.map("TCheckbutton", indicatorbackground=[("disabled", p.surface)])
        style.configure("TNotebook", background=p.surface, bordercolor=p.border)
        style.configure("TNotebook.Tab", background=p.card, foreground=p.text_muted, padding=(10, 3))
        style.map("TNotebook.Tab", background=[("selected", p.surface)],
                  foreground=[("selected", p.text)])
        style.configure("Treeview", background=p.field, foreground=p.text)
        style.configure("Treeview.Heading", background=p.card, foreground=p.text)
        style.map("Treeview.Heading", background=[("active", p.hover)])
        style.map("Treeview", background=[("selected", p.select)],
                  foreground=[("selected", p.select_text)])
        style.configure("Vertical.TScrollbar", background=p.card, bordercolor=p.surface)
    style.configure("Treeview", rowheight=24)
    style.configure("Card.TFrame", background=p.card, relief="solid", borderwidth=1)
    style.configure("CardTitle.TLabel", background=p.card, foreground=p.text_muted, font=("Segoe UI", 9))
    style.configure("CardValue.TLabel", background=p.card, foreground=p.text, font=("Segoe UI", 15, "bold"))

    # Λίστες των combobox και μενού δεν είναι widgets ttk.
    for pattern, bg in (("*TCombobox*Listbox", p.field), ("*Menu", p.card)):
        root.option_add(f"{pattern}.background", bg)
        root.option_add(f"{pattern}.foreground", p.text)
        root.option_add(f"{pattern}.selectBackground", p.select)
        root.option_add(f"{pattern}.selectForeground", p.select_text)
    root.option_add("*Menu.activeBackground", p.select)
    root.option_add("*Menu.activeForeground", p.select_text)
    root.configure(bg=p.surface)
    style_title_bar(root)


def style_title_bar(window: tk.Misc):
    """Σκούρα γραμμή τίτλου στα Windows 10/11 όταν το θέμα είναι σκοτεινό."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1 if _theme == "dark" else 0)
        # DWMWA_USE_IMMERSIVE_DARK_MODE (20, παλαιότερα Windows 10: 19)
        for attribute in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except (AttributeError, OSError):
        pass
