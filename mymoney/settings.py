"""Ρυθμίσεις χρήστη (γλώσσα, θέμα) στο settings.json."""

import json
from pathlib import Path


def read(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def update(path: Path, **values):
    """Αλλάζει μόνο τα δοσμένα κλειδιά· τα υπόλοιπα μένουν ως έχουν."""
    data = read(path)
    data.update(values)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
