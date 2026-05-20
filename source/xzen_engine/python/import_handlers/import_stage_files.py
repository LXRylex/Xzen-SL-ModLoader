from __future__ import annotations

import os
import sys
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

try:
    import py7zr  # type: ignore[import-not-found]
except ImportError:
    py7zr = None


SUPPORTED_ARCHIVE_SUFFIXES = {".zip", ".7z"}


# ===== Xzen Stealth Theme =====
ACCENT   = "#ffffff"
BG_DARK  = "#050505"
PANEL    = "#0a0a0a"
TEXT     = "#eeeeee"
TEXT_DIM = "#888888"
BORDER   = "#333333"
ENABLE_CLR  = "#3CCB7F"
DISABLE_CLR = "#FF6B6B"


# -------- Qt5/6 enum compat (kills pylance warnings) --------
QtFramelessWindowHint = getattr(QtCore.Qt, "FramelessWindowHint", getattr(QtCore.Qt.WindowType, "FramelessWindowHint"))
QtDialog              = getattr(QtCore.Qt, "Dialog", getattr(QtCore.Qt.WindowType, "Dialog"))
QtWindow              = getattr(QtCore.Qt, "Window", getattr(QtCore.Qt.WindowType, "Window"))

QtWA_TranslucentBackground = getattr(QtCore.Qt, "WA_TranslucentBackground", getattr(QtCore.Qt.WidgetAttribute, "WA_TranslucentBackground"))
QtNoFocus                 = getattr(QtCore.Qt, "NoFocus", getattr(QtCore.Qt.FocusPolicy, "NoFocus"))
QtStrongFocus             = getattr(QtCore.Qt, "StrongFocus", getattr(QtCore.Qt.FocusPolicy, "StrongFocus"))

QtLeftButton = getattr(QtCore.Qt, "LeftButton", getattr(QtCore.Qt.MouseButton, "LeftButton"))
QtPointingHandCursor = getattr(QtCore.Qt, "PointingHandCursor", getattr(QtCore.Qt.CursorShape, "PointingHandCursor"))

QtUserRole = getattr(QtCore.Qt, "UserRole", getattr(QtCore.Qt.ItemDataRole, "UserRole"))
QtNoItemFlags = getattr(QtCore.Qt, "NoItemFlags", getattr(QtCore.Qt.ItemFlag, "NoItemFlags"))
# -----------------------------------------------------------


def project_root_from_this_file() -> Path:
    # file: source/xzen_engine/python/import_handlers/import_stage_files.py
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
        raise FileNotFoundError(f"JSON not found:\n{path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def compute_game_destinations(paths_json: Path) -> Tuple[Path, Path]:
    """
    Uses paths.json: assetbundles_dir -> ...\\StreamingAssets\\AssetBundles
    - chartrial02 -> AssetBundles\\map\\scenes
    - .resS      -> Smash_Legends_Data\\Mods   (2 levels up from AssetBundles)
    """
    cfg = load_json(paths_json)
    ab = cfg.get("assetbundles_dir", "")
    if not ab:
        raise KeyError("paths.json missing: 'assetbundles_dir'")

    ab_dir = Path(str(ab))
    scenes_dir = ab_dir / "map" / "scenes"

    # go 2 out: AssetBundles -> StreamingAssets -> Smash_Legends_Data
    smash_data_dir = ab_dir.parent.parent
    mods_dir = smash_data_dir / "Mods"

    return scenes_dir, mods_dir


def iter_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return [path for path in root.rglob("*") if path.is_file()]


def find_stage_pair_from_names(names: list[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (chartrial02_entry, ress_entry) from archive member names.
    We scan ALL folders.
    """
    char_entry = None
    ress_entry = None

    # Find chartrial02 (exact filename, any folder)
    for n in names:
        base = Path(n).name
        if base.lower() == "chartrial02":
            char_entry = n
            break

    if not char_entry:
        return None, None

    # Try find .resS near chartrial02 first (same folder)
    char_parent = str(Path(char_entry).parent).replace("\\", "/").strip(".")
    if char_parent == "":
        char_parent = "."

    same_folder = []
    for n in names:
        p = Path(n)
        if str(p.parent).replace("\\", "/").strip(".") == char_parent:
            same_folder.append(n)

    for n in same_folder:
        base = Path(n).name
        if base.lower().endswith(".ress"):
            ress_entry = n
            break

    # Fallback: any .resS anywhere
    if not ress_entry:
        for n in names:
            base = Path(n).name
            if base.lower().endswith(".ress"):
                ress_entry = n
                break

    return char_entry, ress_entry


def find_stage_pair_in_folder(root: Path) -> Tuple[Optional[Path], Optional[Path]]:
    files = iter_files(root)
    char_file = None
    for path in files:
        if path.name.lower() == "chartrial02":
            char_file = path
            break

    if char_file is None:
        return None, None

    same_folder = [path for path in files if path.parent == char_file.parent]
    for path in same_folder:
        if path.name.lower().endswith(".ress"):
            return char_file, path

    for path in files:
        if path.name.lower().endswith(".ress"):
            return char_file, path

    return char_file, None


def extract_archive_to_dir(archive_path: Path, dest_dir: Path) -> None:
    suffix = archive_path.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(dest_dir)
        return

    if suffix == ".7z":
        if py7zr is None:
            raise RuntimeError("7z support requires py7zr. Install it with: python -m pip install py7zr")
        with py7zr.SevenZipFile(archive_path, "r") as archive:
            archive.extractall(path=dest_dir)
        return

    raise ValueError(f"Unsupported archive format: {archive_path.suffix}")


class CustomTitleBar(QtWidgets.QWidget):
    def __init__(self, parent, title="Import Stage Mod"):
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
        self.btn_close.setFocusPolicy(QtNoFocus)
        self.btn_close.clicked.connect(self.parent.close)
        self.btn_close.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TEXT_DIM}; border: none; font-size: 12px; }}
            QPushButton:hover {{ background-color: {DISABLE_CLR}; color: #000; }}
        """)

        layout.addWidget(self.title_lbl)
        layout.addStretch(1)
        layout.addWidget(self.btn_close)

    def mousePressEvent(self, a0):  # name "a0" avoids pylance override mismatch
        if a0.button() == QtLeftButton:
            self.startPos = a0.globalPos()

    def mouseMoveEvent(self, a0):
        if self.startPos:
            delta = a0.globalPos() - self.startPos
            self.parent.move(self.parent.pos() + delta)
            self.startPos = a0.globalPos()

    def mouseReleaseEvent(self, a0):
        self.startPos = None


class ImportStageUI(QtWidgets.QWidget):
    def __init__(self, preset_file: Optional[Path] = None):
        super().__init__()

        self.ROOT = project_root_from_this_file()
        self.paths_json = self.ROOT / "source" / "profile" / "user_data" / "paths.json"

        # ✅ export location inside project
        self.export_root = self.ROOT / "source" / "mods" / "modded" / "custom_stages"

        self.cfg = {}
        self._preset_file = preset_file

        self.setWindowFlags(QtFramelessWindowHint)
        self.setAttribute(QtWA_TranslucentBackground)
        self.setFixedSize(560, 210)

        self._init_ui()
        self._load_config()
        self._prefill_if_arg()

    def _init_ui(self):
        self.main_container = QtWidgets.QFrame(self)
        self.main_container.setObjectName("root")

        self.main_layout = QtWidgets.QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "Import Stage Mod")
        self.main_layout.addWidget(self.title_bar)

        content = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(content)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(14)

        # File row
        self.file_le = QtWidgets.QLineEdit()
        self.file_le.setPlaceholderText("Select a stage archive (.zip or .7z)...")
        self.file_le.setReadOnly(True)
        self.file_le.setMinimumHeight(34)

        self.btn_browse = QtWidgets.QPushButton("Browse")
        self.btn_browse.setCursor(QtGui.QCursor(QtPointingHandCursor))
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
        self.btn_cancel.setCursor(QtGui.QCursor(QtPointingHandCursor))
        self.btn_cancel.setFixedHeight(34)
        self.btn_cancel.clicked.connect(self.close)

        self.btn_import = QtWidgets.QPushButton("Extract Import")
        self.btn_import.setCursor(QtGui.QCursor(QtPointingHandCursor))
        self.btn_import.setObjectName("AccentBtn")
        self.btn_import.setFixedHeight(34)
        self.btn_import.clicked.connect(self._on_import)

        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_import)

        lab2 = QtWidgets.QLabel("File:")
        lab2.setStyleSheet(f"color:{TEXT}; margin-bottom: 2px;")

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

    def _load_config(self):
        try:
            self.cfg = load_json(self.paths_json)
            self._set_status("Ready")
        except Exception:
            self.cfg = {}
            self._set_status("Ready")

    def _prefill_if_arg(self):
        if self._preset_file and self._preset_file.exists():
            self.file_le.setText(str(self._preset_file))

    def _on_browse(self):
        last_dir = self.cfg.get("last_import_dir", "")
        initial_dir = Path(last_dir) if last_dir and Path(last_dir).exists() else downloads_dir()

        fn, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select a stage archive",
            str(initial_dir),
            "Archive Files (*.zip *.7z);;All Files (*)"
        )
        if not fn:
            return

        fpath = Path(fn)
        self.file_le.setText(str(fpath))

        # remember last directory
        self.cfg["last_import_dir"] = str(fpath.parent)
        try:
            save_json(self.paths_json, self.cfg)
        except Exception:
            pass

    def _on_import(self):
        try:
            file_txt = self.file_le.text().strip()
            if not file_txt:
                QtWidgets.QMessageBox.warning(self, "No File", "Pick a stage archive first.")
                return

            zpath = Path(file_txt)
            if not zpath.exists() or not zpath.is_file():
                QtWidgets.QMessageBox.critical(self, "Error", f"File not found:\n\n{zpath}")
                return

            suffix = zpath.suffix.lower()
            if suffix not in SUPPORTED_ARCHIVE_SUFFIXES:
                QtWidgets.QMessageBox.warning(self, "Wrong format", "Only .zip and .7z are supported.")
                return

            self._set_status("Scanning archive...")

            with tempfile.TemporaryDirectory(prefix="xzen_stage_import_") as temp_dir_text:
                temp_dir = Path(temp_dir_text)
                extract_archive_to_dir(zpath, temp_dir)

                char_path, ress_path = find_stage_pair_in_folder(temp_dir)
                if not char_path:
                    self._set_status("Not found")
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Missing chartrial02",
                        "Could not find file named:\n\nchartrial02\n\ninside this archive."
                    )
                    return

                if not ress_path:
                    self._set_status("Not found")
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Missing .resS",
                        "Found chartrial02 but no .resS file was found in the archive."
                    )
                    return

                ress_name = ress_path.name
                folder_name = Path(ress_name).stem

                out_dir = self.export_root / folder_name
                out_dir.mkdir(parents=True, exist_ok=True)

                # Extract both
                self._set_status("Extracting files...")
                (out_dir / "chartrial02").write_bytes(char_path.read_bytes())
                (out_dir / ress_name).write_bytes(ress_path.read_bytes())

            # Compute destinations based on paths.json
            scenes_dir, mods_dir = compute_game_destinations(self.paths_json)

            # destination.json in the folder
            destination_json = out_dir / "destination.json"
            save_json(destination_json, {
                "chartrial02_dest_dir": str(scenes_dir),
                "ress_dest_dir": str(mods_dir),
            })


            self._set_status("Done ✅")

            QtWidgets.QMessageBox.information(
                self,
                "Imported ✅",
                f"Extracted:\n"
                f" - chartrial02\n"
                f" - {ress_name}\n\n"
                f"To:\n{out_dir}\n\n"
                f"Created:\n{destination_json.name}"
            )
            self.close()

        except zipfile.BadZipFile:
            self._set_status("Error")
            QtWidgets.QMessageBox.critical(
                self,
                "Bad Archive",
                "This archive could not be read by the stage importer.\n\nIf this was a .7z file, it may use a format Python's zip reader cannot unpack.",
            )
        except Exception as e:
            self._set_status("Error")
            QtWidgets.QMessageBox.critical(self, "Error", f"{type(e).__name__}: {e}")


def open_import_stage_ui(preset_file: Optional[str] = None) -> ImportStageUI:
    """
    Call from BAT:
    python import_stage_files.py
    python import_stage_files.py "C:\\path\\file.zip"
    """
    app = QtWidgets.QApplication.instance()
    created = False
    if app is None:
        app = QtWidgets.QApplication(["import_stage_mod"])
        created = True

    ui = ImportStageUI(preset_file=Path(preset_file) if preset_file else None)
    ui.show()

    if created:
        app.exec_()

    return ui


if __name__ == "__main__":
    preset = sys.argv[1] if len(sys.argv) >= 2 else None
    open_import_stage_ui(preset)
