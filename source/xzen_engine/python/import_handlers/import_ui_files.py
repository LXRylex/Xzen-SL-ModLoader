from __future__ import annotations

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Optional

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


class CustomTitleBar(QtWidgets.QWidget):
    def __init__(self, parent, title="Import UI Mod"):
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


class ImportUIModUI(QtWidgets.QWidget):
    def __init__(self, preset_file: Optional[Path] = None):
        super().__init__()

        self.ROOT = project_root_from_this_file()
        self.paths_json = self.ROOT / "source" / "profile" / "user_data" / "paths.json"

        # ✅ destination is always this
        self.dest_root = self.ROOT / "source" / "mods" / "modded" / "ui_mods"

        self.cfg = {}
        self._preset_file = preset_file

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFixedSize(560, 270)

        self._init_ui()
        self._load_config()
        self._prefill_if_arg()

    def _init_ui(self):
        self.main_container = QtWidgets.QFrame(self)
        self.main_container.setObjectName("root")

        self.main_layout = QtWidgets.QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "Import UI Mod")
        self.main_layout.addWidget(self.title_bar)

        content = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(content)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(14)

        # File row
        self.file_le = QtWidgets.QLineEdit()
        self.file_le.setPlaceholderText("Select UI file to import...")
        self.file_le.setReadOnly(True)
        self.file_le.setMinimumHeight(34)

        self.rename_le = QtWidgets.QLineEdit()
        self.rename_le.setPlaceholderText("You can rename it to whatever you want")
        self.rename_le.setMinimumHeight(34)

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

        lab2 = QtWidgets.QLabel("File:")
        lab2.setStyleSheet(f"color:{TEXT}; margin-bottom: 2px;")

        rename_lab = QtWidgets.QLabel("Rename As:")
        rename_lab.setStyleSheet(f"color:{TEXT}; margin-bottom: 2px;")

        lay.addWidget(lab2)
        lay.addLayout(row)
        lay.addWidget(rename_lab)
        lay.addWidget(self.rename_le)
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

    def _load_config(self):
        try:
            self.cfg = load_json(self.paths_json)
            self._set_status("Ready")
        except Exception:
            # if paths.json missing we still allow import, but no "last dir" save
            self.cfg = {}
            self._set_status("Ready")

    def _prefill_if_arg(self):
        if self._preset_file and self._preset_file.exists():
            self.file_le.setText(str(self._preset_file))
            self._set_rename_from_path(self._preset_file)

    def _set_rename_from_path(self, path: Path):
        self.rename_le.setText(path.name)

    def _build_destination_name(self, src: Path) -> str:
        typed_name = self.rename_le.text().strip()
        if not typed_name:
            return src.name

        invalid_chars = set('/\\')
        if any(ch in typed_name for ch in invalid_chars):
            raise ValueError("Rename field must only contain a file name, not a path.")

        if typed_name in {".", ".."}:
            raise ValueError("Rename field must contain a valid file name.")

        candidate = Path(typed_name).name.strip()
        if not candidate:
            raise ValueError("Rename field must contain a valid file name.")

        if Path(candidate).suffix:
            return candidate
        return f"{candidate}{src.suffix}"

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
        self._set_rename_from_path(fpath)

        # remember last directory in your existing paths.json
        self.cfg["last_import_dir"] = str(fpath.parent)
        try:
            save_json(self.paths_json, self.cfg)
        except Exception:
            pass

    def _on_import(self):
        try:
            file_txt = self.file_le.text().strip()
            if not file_txt:
                QtWidgets.QMessageBox.warning(self, "No File", "Pick a file first.")
                return

            src = Path(file_txt)
            if not src.exists() or not src.is_file():
                QtWidgets.QMessageBox.critical(self, "Error", f"File not found:\n\n{src}")
                return

            self.dest_root.mkdir(parents=True, exist_ok=True)
            dst_name = self._build_destination_name(src)
            dst = self.dest_root / dst_name

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
                f"Moved:\n{dst.name}\n\nTo:\n{self.dest_root}"
            )
            self.close()

        except Exception as e:
            self._set_status("Error")
            QtWidgets.QMessageBox.critical(self, "Error", f"{type(e).__name__}: {e}")


def open_import_skin_ui(preset_file: Optional[str] = None) -> ImportUIModUI:
    """
    Call from other scripts or BAT.

    open_import_skin_ui()
    open_import_skin_ui(r"C:\\Users\\You\\Downloads\\file.whatever")
    """
    app = QtWidgets.QApplication.instance()
    created = False
    if app is None:
        app = QtWidgets.QApplication(["import_ui_mod"])
        created = True

    ui = ImportUIModUI(preset_file=Path(preset_file) if preset_file else None)
    ui.show()

    if created:
        app.exec_()

    return ui


# ✅ allow running directly from BAT too
if __name__ == "__main__":
    preset = sys.argv[1] if len(sys.argv) >= 2 else None
    open_import_skin_ui(preset)
