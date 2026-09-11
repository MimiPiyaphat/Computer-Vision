"""Validated design tokens; reloaded in the dashboard with F5."""

import json
from pathlib import Path
import re

THEME_PATH = Path(__file__).with_name("theme.json")
COLORS = ("background", "surface", "preview", "text", "muted", "accent", "accent_text", "warning", "danger")


def load_theme(path=THEME_PATH):
    tokens = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in COLORS:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(tokens.get(key, ""))):
            raise ValueError(f"Theme token '{key}' must be a six-digit hex color.")
    for key, minimum, maximum in (("font_size", 9, 18), ("spacing", 8, 32)):
        value = tokens.get(key)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"Theme token '{key}' must be an integer from {minimum} to {maximum}.")
    if not isinstance(tokens.get("font"), str) or not tokens["font"].strip():
        raise ValueError("Theme token 'font' must be a nonempty font name.")
    return tokens
