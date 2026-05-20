from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PyQt5 import QtWidgets


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


APP_SETTINGS_JSON = project_root() / "source" / "profile" / "user_data" / "app_settings.json"
DEFAULT_THEME = "dark"

PALETTES = {
    "dark": {
        "ACCENT": "#ffffff",
        "BG_DARK": "#050505",
        "PANEL": "#0a0a0a",
        "SURFACE": "#101010",
        "TEXT": "#eeeeee",
        "TEXT_DIM": "#888888",
        "BORDER": "#333333",
        "INPUT_BG": "#111111",
        "CARD_ALT": "#0d0d0d",
        "HOVER_BG": "#151515",
        "SELECT_BG": "#1a1a1a",
        "SOFT_BG": "#202020",
        "TRACK_OFF": "#252525",
        "PRIMARY_BG": "#eeeeee",
        "PRIMARY_HOVER": "#ffffff",
        "PRIMARY_PRESSED": "#dcdcdc",
        "PRIMARY_TEXT": "#050505",
        "DIALOG_BG": "#141414",
        "DIALOG_EDGE": "#2a2a2a",
        "DIALOG_DIM": "#bdbdbd",
        "SCROLLBAR": "#222222",
        "SCROLLBAR_HOVER": "#333333",
    },
    "light": {
        "ACCENT": "#111111",
        "BG_DARK": "#ffffff",
        "PANEL": "#f5f5f5",
        "SURFACE": "#ededed",
        "TEXT": "#111111",
        "TEXT_DIM": "#5a5a5a",
        "BORDER": "#b8b8b8",
        "INPUT_BG": "#ffffff",
        "CARD_ALT": "#f0f0f0",
        "HOVER_BG": "#ececec",
        "SELECT_BG": "#e3e3e3",
        "SOFT_BG": "#dedede",
        "TRACK_OFF": "#cfcfcf",
        "PRIMARY_BG": "#111111",
        "PRIMARY_HOVER": "#000000",
        "PRIMARY_PRESSED": "#2a2a2a",
        "PRIMARY_TEXT": "#ffffff",
        "DIALOG_BG": "#ffffff",
        "DIALOG_EDGE": "#c7c7c7",
        "DIALOG_DIM": "#555555",
        "SCROLLBAR": "#2b2b2b",
        "SCROLLBAR_HOVER": "#111111",
    },
}


def load_theme_name() -> str:
    if APP_SETTINGS_JSON.exists():
        try:
            raw = json.loads(APP_SETTINGS_JSON.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and str(raw.get("theme", "")).strip().lower() == "light":
                return "light"
        except Exception:
            pass
    return DEFAULT_THEME


def is_light_theme() -> bool:
    return load_theme_name() == "light"


def theme_colors() -> dict[str, str]:
    return dict(PALETTES[load_theme_name()])


def theme_qss(qss: str) -> str:
    if not qss or not is_light_theme():
        return qss

    replacements = [
        ("rgba(255, 255, 255,", "rgba(0, 0, 0,"),
        ("rgba(255,255,255,", "rgba(0,0,0,"),
        ("#050505", "#ffffff"),
        ("#0a0a0a", "#f5f5f5"),
        ("#0b0b0b", "#f2f2f2"),
        ("#0d0d0d", "#f0f0f0"),
        ("#101010", "#ededed"),
        ("#111111", "#ffffff"),
        ("#120d19", "#f1eef7"),
        ("#141414", "#fbfbfb"),
        ("#151515", "#ececec"),
        ("#161616", "#e9e9e9"),
        ("#171717", "#e7e7e7"),
        ("#1a0d0d", "#f8eded"),
        ("#1a1323", "#f1eef7"),
        ("#1a1a1a", "#e3e3e3"),
        ("#1b1b1b", "#e1e1e1"),
        ("#1c1c1c", "#dfdfdf"),
        ("#202020", "#dedede"),
        ("#222222", "#2a2a2a"),
        ("#222", "#2a2a2a"),
        ("#241111", "#f4e4e4"),
        ("#252525", "#cfcfcf"),
        ("#2a2a2a", "#b8b8b8"),
        ("#2b2b2b", "#b0b0b0"),
        ("#2d2d2d", "#a8a8a8"),
        ("#333333", "#8f8f8f"),
        ("#333", "#8f8f8f"),
        ("#555555", "#777777"),
        ("#666666", "#9d9d9d"),
        ("#888888", "#5a5a5a"),
        ("#bdbdbd", "#555555"),
        ("#cccccc", "#2a2a2a"),
        ("#dcdcdc", "#222222"),
        ("#dedede", "#1e1e1e"),
        ("#e8e8e8", "#111111"),
        ("#eaeaea", "#111111"),
        ("#eeeeee", "#111111"),
        ("#f0f0f0", "#000000"),
        ("#f3f3f3", "#050505"),
        ("#ffffff", "#111111"),
        ("#000000", "#ffffff"),
        ("#000", "#ffffff"),
    ]

    themed = qss
    for old, new in replacements:
        themed = re.sub(re.escape(old), new, themed, flags=re.IGNORECASE)
    return themed


def install_stylesheet_hook() -> None:
    if getattr(QtWidgets.QWidget, "_xzen_theme_hooked", False):
        return

    original = QtWidgets.QWidget.setStyleSheet

    def themed_set_stylesheet(self, style):
        if isinstance(style, str):
            style = theme_qss(style)
        return original(self, style)

    QtWidgets.QWidget.setStyleSheet = themed_set_stylesheet
    QtWidgets.QWidget._xzen_theme_hooked = True


install_stylesheet_hook()
