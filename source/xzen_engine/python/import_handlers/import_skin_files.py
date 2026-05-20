from __future__ import annotations

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Optional, Dict, List

from PyQt5 import QtCore, QtGui, QtWidgets

# ===== Xzen Stealth Theme =====
ACCENT   = "#ffffff"
BG_DARK  = "#050505"
PANEL    = "#0a0a0a"
TEXT     = "#eeeeee"
TEXT_DIM = "#888888"
BORDER   = "#333333"
ENABLE_CLR  = "#3CCB7F"
DISABLE_CLR = "#FF6B6B"


def project_root_from_this_file() -> Path:
    # file: source/xzen_engine/python/import_handlers/import_skin_files.py
    # parents:
    # 0 import_handlers
    # 1 python
    # 2 xzen_engine
    # 3 source
    # 4 project root
    return Path(__file__).resolve().parents[4]


def downloads_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        p = Path(userprofile) / "Downloads"
        if p.exists():
            return p
    return Path.home() / "Downloads"


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"paths.json not found:\n{path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_character_map(characters_dir: Path) -> Dict[str, str]:
    # {lower: actual}
    out: Dict[str, str] = {}
    if not characters_dir.exists():
        return out
    for p in characters_dir.iterdir():
        if p.is_dir():
            out[p.name.lower()] = p.name
    return out


class CustomTitleBar(QtWidgets.QWidget):
    def __init__(self, parent, title="Import Skin File"):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(35)
        self.startPos = None

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(10)

        self.title_lbl = QtWidgets.QLabel(title)
        self.title_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-weight: 600; font-size: 12px;")

        self.btn_close = QtWidgets.QPushButton("✕")
        self.btn_close.setFixedSize(45, 35)
        self.btn_close.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_close.clicked.connect(self.parent.close)
        self.btn_close.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TEXT_DIM}; border: none; font-size: 12px; }}
            QPushButton:hover {{ background-color: {DISABLE_CLR}; color: #000; }}
        """)

        layout.addWidget(self.title_lbl)
        layout.addStretch(1)
        layout.addWidget(self.btn_close)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.startPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.startPos:
            delta = event.globalPos() - self.startPos
            self.parent.move(self.parent.pos() + delta)
            self.startPos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.startPos = None


class ImportSkinUI(QtWidgets.QWidget):
    def __init__(self, preset_file: Optional[Path] = None):
        super().__init__()

        self.ROOT = project_root_from_this_file()
        self.paths_json = self.ROOT / "source" / "profile" / "user_data" / "paths.json"
        self.dest_root = self.ROOT / "source" / "mods" / "modded" / "characters"

        self.cfg = {}
        self.character_map: Dict[str, str] = {}
        self.character_list: List[str] = []
        self.characters_dir: Optional[Path] = None

        self._preset_file = preset_file

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFixedSize(560, 300)

        self._init_ui()
        self._load_config_and_scan()
        self._prefill_if_arg()

    def _init_ui(self):
        self.main_container = QtWidgets.QFrame(self)
        self.main_container.setObjectName("root")

        self.main_layout = QtWidgets.QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "Import Skin File")
        self.main_layout.addWidget(self.title_bar)

        content = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(content)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(14)

        # Character input
        self.char_le = QtWidgets.QLineEdit()
        self.char_le.setPlaceholderText("Character Name (autocomplete enabled)")
        self.char_le.setMinimumHeight(34)

        # File row
        self.file_le = QtWidgets.QLineEdit()
        self.file_le.setPlaceholderText("Select any file to import...")
        self.file_le.setReadOnly(True)
        self.file_le.setMinimumHeight(34)

        self.btn_browse = QtWidgets.QPushButton("Browse")
        self.btn_browse.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.btn_browse.setFixedHeight(34)
        self.btn_browse.setFixedWidth(90)
        self.btn_browse.clicked.connect(self._on_browse)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.file_le, 1)
        row.addWidget(self.btn_browse, 0, QtCore.Qt.AlignVCenter)

        self.status = QtWidgets.QLabel("Ready")
        self.status.setStyleSheet(f"color:{TEXT_DIM}; font-size: 11px;")

        btns = QtWidgets.QHBoxLayout()
        btns.setSpacing(10)
        btns.addStretch(1)

        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_cancel.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.btn_cancel.setFixedHeight(34)
        self.btn_cancel.clicked.connect(self.close)

        self.btn_import = QtWidgets.QPushButton("Move Import")
        self.btn_import.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.btn_import.setObjectName("AccentBtn")
        self.btn_import.setFixedHeight(34)
        self.btn_import.clicked.connect(self._on_import)

        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_import)

        lab1 = QtWidgets.QLabel("Character:")
        lab2 = QtWidgets.QLabel("File:")
        lab1.setStyleSheet(f"color:{TEXT}; margin-bottom: 2px;")
        lab2.setStyleSheet(f"color:{TEXT}; margin-bottom: 2px;")

        lay.addWidget(lab1)
        lay.addWidget(self.char_le)
        lay.addSpacing(4)
        lay.addWidget(lab2)
        lay.addLayout(row)
        lay.addWidget(self.status)
        lay.addLayout(btns)

        self.main_layout.addWidget(content)

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.main_container)

        self.setStyleSheet(self._qss())

    def _qss(self) -> str:
        return f"""
        * {{ outline: none; }}
        QWidget {{
            background: {BG_DARK};
            color: {TEXT};
            font-family: "Segoe UI", sans-serif;
            font-size: 13px;
        }}

        QFrame#root {{
            border: 1px solid {BORDER};
            border-radius: 6px;
            background: {BG_DARK};
        }}

        QLineEdit {{
            background: {PANEL};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 5px;
            padding: 8px 10px;
            min-height: 18px;
        }}
        QLineEdit:focus {{
            border: 1px solid {TEXT_DIM};
        }}

        QLabel {{
            color: {TEXT};
        }}

        QPushButton {{
            background: transparent;
            color: {TEXT_DIM};
            border: 1px solid {BORDER};
            padding: 7px 14px;
            border-radius: 4px;
            font-weight: 700;
        }}
        QPushButton:hover {{
            color: {TEXT};
            border-color: {TEXT_DIM};
            background: #111111;
        }}

        QPushButton#AccentBtn {{
            background: {TEXT};
            color: {BG_DARK};
            border: 1px solid {TEXT};
            font-weight: 800;
        }}
        QPushButton#AccentBtn:hover {{
            background: #ffffff;
        }}
        QPushButton:disabled {{
            background: #222;
            color: #555;
            border-color: #333;
        }}
        """

    def _set_status(self, txt: str):
        self.status.setText(txt)

    # ---- Autocomplete setup (HOVER SELECT FIX) ----
    def _apply_autocomplete(self):
        if not self.character_list:
            return

        completer = QtWidgets.QCompleter(self.character_list, self)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        completer.setMaxVisibleItems(14)

        popup = completer.popup()  # QListView
        popup.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        popup.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        # Enable hover tracking
        popup.setMouseTracking(True)
        popup.viewport().setMouseTracking(True)

        # Dropdown height (adjust here)
        POPUP_H = 260
        popup.setMinimumHeight(POPUP_H)
        popup.setMaximumHeight(POPUP_H)

        # Width matches input
        popup.setMinimumWidth(self.char_le.width())

        # Force "hover" to become "selected"
        popup.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        popup.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        def _hover_select(index: QtCore.QModelIndex):
            try:
                popup.setCurrentIndex(index)
                popup.selectionModel().setCurrentIndex(
                    index,
                    QtCore.QItemSelectionModel.ClearAndSelect
                )
            except Exception:
                pass

        popup.entered.connect(_hover_select)

        popup.setStyleSheet(f"""
            QListView {{
                background: {PANEL};
                color: {TEXT};
                border: 1px solid {BORDER};
                padding: 6px;
                outline: none;

                font-size: 15px;
                font-weight: 600;
            }}

            QListView::item {{
                padding: 10px 12px;
                border-radius: 6px;
            }}

            QListView::item:selected {{
                background: #1a1a1a;  /* hover becomes selected ✅ */
                color: {TEXT};
            }}

            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: #2d2d2d;
                min-height: 32px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #3a3a3a;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)

        self.char_le.setCompleter(completer)

        # keep popup width synced
        def _sync_popup_width():
            try:
                popup.setMinimumWidth(self.char_le.width())
            except Exception:
                pass

        self.char_le.textEdited.connect(lambda _: _sync_popup_width())

    def _load_config_and_scan(self):
        try:
            self.cfg = load_json(self.paths_json)
            assetbundles_dir = Path(self.cfg.get("assetbundles_dir", "")).expanduser()
            self.characters_dir = assetbundles_dir / "characters"

            if not self.characters_dir.exists():
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Characters folder not found:\n\n{self.characters_dir}\n\nCheck paths.json -> assetbundles_dir"
                )
                self.btn_import.setEnabled(False)
                self.btn_browse.setEnabled(False)
                self._set_status("Error: characters folder missing")
                return

            self.character_map = build_character_map(self.characters_dir)
            if not self.character_map:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"No character folders found in:\n\n{self.characters_dir}"
                )
                self.btn_import.setEnabled(False)
                self.btn_browse.setEnabled(False)
                self._set_status("Error: no character folders")
                return

            self.character_list = sorted(self.character_map.values(), key=lambda s: s.lower())
            self._apply_autocomplete()
            self._set_status("Ready")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"{type(e).__name__}: {e}")
            self.btn_import.setEnabled(False)
            self.btn_browse.setEnabled(False)
            self._set_status("Error: config load failed")

    def _prefill_if_arg(self):
        if self._preset_file and self._preset_file.exists():
            self.file_le.setText(str(self._preset_file))

    def _on_browse(self):
        last_dir = self.cfg.get("last_import_dir", "")
        initial_dir = Path(last_dir) if last_dir and Path(last_dir).exists() else downloads_dir()

        fn, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select a file to import",
            str(initial_dir),
            "All Files (*.*)"
        )
        if not fn:
            return

        fpath = Path(fn)
        self.file_le.setText(str(fpath))

        self.cfg["last_import_dir"] = str(fpath.parent)
        try:
            save_json(self.paths_json, self.cfg)
        except Exception:
            pass

    def _resolve_character(self, user_text: str) -> Optional[str]:
        key = (user_text or "").strip().lower()
        if not key:
            return None
        return self.character_map.get(key)

    def _on_import(self):
        try:
            char_input = self.char_le.text().strip()
            real_folder = self._resolve_character(char_input)
            if not real_folder:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Invalid Character",
                    "Character name must match a folder inside:\nAssetBundles\\characters\n\n(case-insensitive)\n\nTip: hover-select dropdown works now."
                )
                return

            file_txt = self.file_le.text().strip()
            if not file_txt:
                QtWidgets.QMessageBox.warning(self, "No File", "Pick a file first.")
                return

            src = Path(file_txt)
            if not src.exists() or not src.is_file():
                QtWidgets.QMessageBox.critical(self, "Error", f"File not found:\n\n{src}")
                return

            target_dir = self.dest_root / real_folder
            target_dir.mkdir(parents=True, exist_ok=True)
            dst = target_dir / src.name

            if dst.exists():
                ok = QtWidgets.QMessageBox.question(
                    self,
                    "Overwrite?",
                    f"File already exists:\n\n{dst.name}\n\nOverwrite it?"
                )
                if ok != QtWidgets.QMessageBox.Yes:
                    return

            self._set_status("Moving file...")
            shutil.move(str(src), str(dst))
            self._set_status("Done ✅")

            QtWidgets.QMessageBox.information(
                self,
                "Imported ✅",
                f"Moved:\n{dst.name}\n\nTo:\n{target_dir}"
            )
            self.close()

        except Exception as e:
            self._set_status("Error")
            QtWidgets.QMessageBox.critical(self, "Error", f"{type(e).__name__}: {e}")


def open_import_skin_ui(preset_file: Optional[str] = None) -> ImportSkinUI:
    """
    Use from other scripts or BAT.
    If no QApplication exists -> create it and exec.
    If it already exists -> just show UI.
    """
    app = QtWidgets.QApplication.instance()
    created = False
    if app is None:
        app = QtWidgets.QApplication(["import_skin_files"])
        created = True

    ui = ImportSkinUI(preset_file=Path(preset_file) if preset_file else None)
    ui.show()

    if created:
        app.exec_()

    return ui


# ✅ makes BAT work (when running this file directly)
if __name__ == "__main__":
    preset = sys.argv[1] if len(sys.argv) >= 2 else None
    open_import_skin_ui(preset)
