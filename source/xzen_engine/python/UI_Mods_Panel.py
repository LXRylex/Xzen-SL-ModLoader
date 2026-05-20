from __future__ import annotations

import sys
import json
import shutil
from pathlib import Path
from typing import Optional, List

from PyQt5 import QtCore, QtGui, QtWidgets

# ===========================
# Debug flags
# ===========================
DEBUG_TERMINAL = False  # True/False: prints to real terminal
DEBUG_UI_LOG   = False  # True/False: shows the in-app log box

# ===== Xzen Stealth Theme =====
BG_DARK   = "#050505"
PANEL     = "#0a0a0a"
TEXT      = "#eeeeee"
TEXT_DIM  = "#888888"
BORDER    = "#333333"
RED_NSFw  = "#ff4d4d"
CLOSE_RED = "#ff4d4d"

GREEN_OK  = "#3CCB7F"


# ---------------- Paths ----------------
def project_root_from_this_file() -> Path:
    # file: source/xzen_engine/python/UI_Mods_Panel.py
    # parents:
    # 0 python
    # 1 xzen_engine
    # 2 source
    # 3 project root
    return Path(__file__).resolve().parents[3]


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSON:\n{path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def safe_print(msg: str) -> None:
    try:
        sys.stdout.buffer.write((msg + "\n").encode("utf-8", "replace"))
        sys.stdout.flush()
    except Exception:
        pass


def game_character_dir_from_paths_json(paths_json: Path) -> Path:
    cfg = load_json(paths_json)
    ab = cfg.get("assetbundles_dir", "")
    if not ab:
        raise RuntimeError("paths.json missing: assetbundles_dir")

    base = Path(ab)  # ends with .../AssetBundles
    target = base / "data" / "scriptableobjects" / "character"
    return target


# ---------------- UI helpers ----------------
class CustomTitleBar(QtWidgets.QWidget):
    def __init__(self, parent, title="UI Mods Panel"):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(35)
        self.startPos = None

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 0, 0)
        lay.setSpacing(10)

        self.title_lbl = QtWidgets.QLabel(title)
        self.title_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-weight: 600; font-size: 12px;")

        self.btn_close = QtWidgets.QPushButton("✕")
        self.btn_close.setFixedSize(45, 35)
        self.btn_close.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_close.clicked.connect(self.parent.close)

        # ✅ red outline idle
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_DIM};
                border: 1px solid {CLOSE_RED};
                font-size: 12px;
                border-radius: 0px;
            }}
            QPushButton:hover {{
                background-color: {CLOSE_RED};
                color: #000;
                border: 1px solid {CLOSE_RED};
            }}
        """)

        lay.addWidget(self.title_lbl)
        lay.addStretch(1)
        lay.addWidget(self.btn_close)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self.startPos = e.globalPos()

    def mouseMoveEvent(self, e):
        if self.startPos:
            delta = e.globalPos() - self.startPos
            self.parent.move(self.parent.pos() + delta)
            self.startPos = e.globalPos()

    def mouseReleaseEvent(self, e):
        self.startPos = None


class ToggleSwitch(QtWidgets.QAbstractButton):
    """
    ✅ Proper toggle switch (no checkbox indicator hack)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.setFixedSize(52, 26)
        self.setFocusPolicy(QtCore.Qt.NoFocus)

    def sizeHint(self):
        return QtCore.QSize(52, 26)

    def paintEvent(self, _):
        w = self.width()
        h = self.height()

        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        pad = 1
        rect = QtCore.QRectF(pad, pad, w - pad * 2, h - pad * 2)

        if self.isChecked():
            track = QtGui.QColor("#ffffff")
            border = QtGui.QColor("#ffffff")
            knob = QtGui.QColor(PANEL)
        else:
            track = QtGui.QColor("#1a1a1a")
            border = QtGui.QColor(BORDER)
            knob = QtGui.QColor("#ffffff")

        p.setPen(QtGui.QPen(border, 1))
        p.setBrush(track)
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        knob_d = h - 6
        y = (h - knob_d) / 2
        x_off = 3
        x = (w - x_off - knob_d) if self.isChecked() else x_off

        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(knob)
        p.drawEllipse(QtCore.QRectF(x, y, knob_d, knob_d))
        p.end()


class ModRow(QtWidgets.QWidget):
    toggled = QtCore.pyqtSignal(object, bool)

    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(12)

        self.label = QtWidgets.QLabel()
        self.label.setTextFormat(QtCore.Qt.RichText)

        if "nsfw" in filename.lower():
            safe_name = filename.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            marked = safe_name.replace("NSFW", f"<span style='color:{RED_NSFw}; font-weight:800;'>NSFW</span>")
            marked = marked.replace("nsfw", f"<span style='color:{RED_NSFw}; font-weight:800;'>nsfw</span>")
            self.label.setText(marked)
        else:
            self.label.setText(filename)

        self.label.setStyleSheet(f"color:{TEXT}; font-size: 13px;")

        self.switch = ToggleSwitch()
        self.switch.toggled.connect(lambda state: self.toggled.emit(self, state))

        lay.addWidget(self.label, 1)
        lay.addWidget(self.switch, 0, QtCore.Qt.AlignVCenter)

        self.setStyleSheet(f"""
            QWidget {{
                background: transparent;
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
        """)

    def set_on(self, on: bool, block_signal: bool = True):
        if block_signal:
            self.switch.blockSignals(True)
        self.switch.setChecked(on)
        if block_signal:
            self.switch.blockSignals(False)

    def is_on(self) -> bool:
        return self.switch.isChecked()


# ---------------- Main UI ----------------
class UIModsPanel(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.ROOT = project_root_from_this_file()

        self.MODDED_DIR = self.ROOT / "source" / "mods" / "modded" / "ui_mods"
        self.BACKUP_DIR = self.ROOT / "source" / "mods" / "backup" / "ui_mods"

        self.PATHS_JSON = self.ROOT / "source" / "profile" / "user_data" / "paths.json"
        self.STATE_JSON = self.ROOT / "source" / "profile" / "user_data" / "ui_mods_panel.json"

        self.game_char_dir: Optional[Path] = None
        self.game_ui_path: Optional[Path] = None
        self.backup_ui_path: Optional[Path] = None

        self.rows: List[ModRow] = []
        self.active_mod: Optional[str] = None

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFixedSize(620, 520)

        self._restore_btn_default_style = ""

        self._init_ui()
        self._load_paths()
        self._ensure_backup_folder()
        self._load_state()
        self._load_mods()
        self._apply_state_to_ui()

    # -------- UI setup --------
    def _init_ui(self):
        self.root_frame = QtWidgets.QFrame(self)
        self.root_frame.setObjectName("root")

        main = QtWidgets.QVBoxLayout(self.root_frame)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "UI Mods Panel")
        main.addWidget(self.title_bar)

        body = QtWidgets.QWidget()
        body_lay = QtWidgets.QVBoxLayout(body)
        body_lay.setContentsMargins(18, 16, 18, 16)
        body_lay.setSpacing(12)

        self.info = QtWidgets.QLabel("Choose 1 UI mod. Turning OFF restores original UI.")
        self.info.setStyleSheet(f"color:{TEXT_DIM}; font-size: 12px;")
        body_lay.addWidget(self.info)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.list_host = QtWidgets.QWidget()
        self.list_lay = QtWidgets.QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(10)
        self.list_lay.addStretch(1)

        self.scroll.setWidget(self.list_host)
        body_lay.addWidget(self.scroll, 1)

        # in-app logs
        self.status = QtWidgets.QTextEdit()
        self.status.setReadOnly(True)
        self.status.setFixedHeight(92)
        self.status.setStyleSheet(f"""
            QTextEdit {{
                background: {PANEL};
                color: {TEXT_DIM};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 8px;
                font-family: Consolas, monospace;
                font-size: 11px;
            }}
        """)
        self.status.setPlaceholderText("Status output...")

        if DEBUG_UI_LOG:
            body_lay.addWidget(self.status)
        else:
            self.status.hide()

        btns = QtWidgets.QHBoxLayout()
        btns.addStretch(1)

        self.btn_restore = QtWidgets.QPushButton("Restore Original")
        self.btn_restore.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.btn_restore.clicked.connect(self._restore_original_clicked)

        self.btn_close = QtWidgets.QPushButton("Close")
        self.btn_close.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.btn_close.clicked.connect(self.close)

        btns.addWidget(self.btn_restore)
        btns.addWidget(self.btn_close)
        body_lay.addLayout(btns)

        main.addWidget(body)

        wrap = QtWidgets.QVBoxLayout(self)
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.addWidget(self.root_frame)

        self.setStyleSheet(self._qss())

        # capture default restore style after qss is applied
        self._restore_btn_default_style = self.btn_restore.styleSheet() or ""

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
            border-radius: 8px;
            background: {BG_DARK};
        }}

        QScrollArea {{
            background: transparent;
        }}

        QPushButton {{
            background: transparent;
            color: {TEXT_DIM};
            border: 1px solid {BORDER};
            padding: 8px 14px;
            border-radius: 6px;
            font-weight: 700;
        }}
        QPushButton:hover {{
            color: {TEXT};
            border-color: {TEXT_DIM};
            background: #111111;
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
        """

    def _log(self, s: str):
        if DEBUG_UI_LOG:
            self.status.append(s)
        if DEBUG_TERMINAL:
            safe_print(s)

    # ✅ button green flash when both debugs are OFF
    def _flash_restore_success(self):
        if DEBUG_TERMINAL or DEBUG_UI_LOG:
            return

        self.btn_restore.setStyleSheet(f"""
            QPushButton {{
                background: {GREEN_OK};
                color: #000;
                border: 1px solid {GREEN_OK};
                padding: 8px 14px;
                border-radius: 6px;
                font-weight: 800;
            }}
        """)

        QtCore.QTimer.singleShot(900, lambda: self.btn_restore.setStyleSheet(self._restore_btn_default_style))

    # -------- File + game paths --------
    def _load_paths(self):
        try:
            self.game_char_dir = game_character_dir_from_paths_json(self.PATHS_JSON)
            self.game_ui_path = self.game_char_dir / "ui"
            self.backup_ui_path = self.BACKUP_DIR / "ui_original"

            self._log(f"[paths] game character dir: {self.game_char_dir}")
            self._log(f"[paths] ui target file: {self.game_ui_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"{type(e).__name__}: {e}")
            self.game_char_dir = None
            self.game_ui_path = None

    def _ensure_backup_folder(self):
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def _ensure_original_backup(self):
        if not self.game_ui_path or not self.backup_ui_path:
            return

        if not self.game_ui_path.exists():
            raise FileNotFoundError(f"Original UI file not found:\n{self.game_ui_path}")

        if not self.backup_ui_path.exists():
            shutil.copy2(str(self.game_ui_path), str(self.backup_ui_path))
            self._log(f"[backup] saved original ui -> {self.backup_ui_path}")

    # -------- State --------
    def _load_state(self):
        self.active_mod = None
        if self.STATE_JSON.exists():
            try:
                data = load_json(self.STATE_JSON)
                self.active_mod = data.get("active_mod") or None
            except Exception:
                self.active_mod = None

    def _save_state(self, active_mod: Optional[str]):
        try:
            save_json(self.STATE_JSON, {"active_mod": active_mod or ""})
        except Exception:
            pass

    # -------- Mod list --------
    def _load_mods(self):
        self.rows.clear()

        while self.list_lay.count() > 1:
            item = self.list_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.MODDED_DIR.mkdir(parents=True, exist_ok=True)

        mods = sorted([p for p in self.MODDED_DIR.iterdir() if p.is_file()], key=lambda p: p.name.lower())

        if not mods:
            hint = QtWidgets.QLabel("No UI mods found.\nPut files into: source/mods/modded/ui_mods")
            hint.setStyleSheet(f"color:{TEXT_DIM}; padding: 16px; border: 1px dashed {BORDER}; border-radius: 8px;")
            self.list_lay.insertWidget(0, hint)
            return

        for p in mods:
            row = ModRow(p.name)
            row.toggled.connect(self._on_row_toggled)
            self.rows.append(row)
            self.list_lay.insertWidget(self.list_lay.count() - 1, row)

    def _apply_state_to_ui(self):
        if not self.active_mod:
            return
        for r in self.rows:
            r.set_on(r.filename == self.active_mod)

    # -------- Toggle logic --------
    def _disable_all_except(self, keep: ModRow):
        for r in self.rows:
            if r is not keep and r.is_on():
                r.set_on(False)

    def _restore_original_clicked(self):
        for r in self.rows:
            r.set_on(False)
        ok = self._restore_original()
        if ok:
            self._flash_restore_success()

    def _restore_original(self) -> bool:
        if not self.game_ui_path or not self.backup_ui_path:
            QtWidgets.QMessageBox.critical(self, "Error", "Game UI path not resolved. Check paths.json.")
            return False

        try:
            if not self.backup_ui_path.exists():
                self._ensure_original_backup()

            shutil.copy2(str(self.backup_ui_path), str(self.game_ui_path))
            self.active_mod = None
            self._save_state(None)
            return True

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"{type(e).__name__}: {e}")
            return False

    def _apply_mod(self, mod_file: Path):
        if not self.game_ui_path:
            QtWidgets.QMessageBox.critical(self, "Error", "Game folder not resolved. Check paths.json.")
            return
        try:
            self._ensure_original_backup()
            shutil.copy2(str(mod_file), str(self.game_ui_path))
            self.active_mod = mod_file.name
            self._save_state(self.active_mod)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"{type(e).__name__}: {e}")

    def _on_row_toggled(self, row: ModRow, state: bool):
        if state:
            self._disable_all_except(row)
            mod_path = self.MODDED_DIR / row.filename
            if not mod_path.exists():
                QtWidgets.QMessageBox.critical(self, "Error", f"Missing mod file:\n{mod_path}")
                row.set_on(False)
                return
            self._apply_mod(mod_path)
        else:
            if self.active_mod == row.filename:
                self._restore_original()


def open_ui_mods_panel() -> UIModsPanel:
    app = QtWidgets.QApplication.instance()
    created = False
    if app is None:
        app = QtWidgets.QApplication(["ui_mods_panel"])
        created = True

    ui = UIModsPanel()
    ui.show()

    if created:
        app.exec_()

    return ui


if __name__ == "__main__":
    open_ui_mods_panel()
