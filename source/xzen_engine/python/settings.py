# settings.py - Minimal Settings with Auto-locate for Smash Legends + Custom Stealth Popups
from PyQt5 import QtCore, QtGui, QtWidgets
from pathlib import Path
import shutil
import importlib.util
import os, sys, json, re, subprocess, threading
from typing import List, Optional, IO

# ===== toggles =====
RESTORE_NEW_CONSOLE           = False   # True = open a separate cmd window; False = no window
RESTORE_STREAM_TO_VSCODE      = True    # True = pipe BAT output to this Python stdout (VS Code terminal)
RESTORE_SHOW_POST_START_TOAST = False   # True = show a toast after starting the script
# ===================

# ---------- EXE-safe project root ----------
def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]
PROJECT_ROOT = project_root()
BASE_DIR = PROJECT_ROOT / "source" / "xzen_engine" / "python"  # .../source/xzen_engine/python
STATE_DIR = PROJECT_ROOT / "source" / "profile" / "user_data"
STATE_DIR.mkdir(parents=True, exist_ok=True)
PATHS_JSON = STATE_DIR / "paths.json"
APP_SETTINGS_JSON = STATE_DIR / "app_settings.json"
# --------------------------------------


def load_module_from_path(mod_name: str, file_path: Path):
    if not file_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(mod_name, str(file_path))
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod

# ===== Stealth Theme Colors =====
ACCENT   = "#ffffff"   # High contrast white
BG_DARK  = "#050505"   # Deep black
PANEL    = "#0a0a0a"   # Panel background
TEXT     = "#eeeeee"   # Main text
TEXT_DIM = "#888888"   # Dim text
BORDER   = "#333333"   # Subtle border

GREEN = "#3CCB7F"
AMBER = "#F1C26E"
RED   = "#FF6B6B"

APPID = 1352080
GAME_HINTS = ("smash", "legend")  # to pick the right exe


# ============================================================
# Custom stealth popup dialog (replaces QMessageBox)
# ============================================================
class StealthPopup(QtWidgets.QDialog):
    def __init__(self, title: str, msg: str, kind: str = "info", buttons=("OK",), parent=None):
        super().__init__(parent)
        self._result = 0

        # single-tone grey UI
        UI_BG   = "#141414"
        UI_EDGE = "#2a2a2a"
        UI_TXT  = "#eaeaea"
        UI_DIM  = "#bdbdbd"

        # compact
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)  # no second layer
        self.setFixedSize(440, 170)

        # hard-override the app-wide QWidget background
        self.setStyleSheet(f"""
            QDialog, QWidget {{
                background: {UI_BG};
            }}
            QLabel {{
                background: transparent;
            }}
        """)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        frame = QtWidgets.QFrame(objectName="F")
        frame.setStyleSheet(f"""
            QFrame#F {{
                background: {UI_BG};
                border: 1px solid {UI_EDGE};
                border-radius: 10px;
            }}
            QLabel#T {{
                color: {UI_TXT};
                font-weight: 800;
                font-size: 14px;
                background: transparent;
            }}
            QLabel#M {{
                color: {UI_DIM};
                font-size: 13px;
                background: transparent;
            }}
            QPushButton#X {{
                background: transparent;
                border: 1px solid {UI_EDGE};
                color: {UI_TXT};
                min-width: 30px; max-width: 30px;
                min-height: 24px; max-height: 24px;
                border-radius: 7px;
                font-weight: 900;
            }}
            QPushButton#X:hover {{
                background: #1c1c1c;
                border-color: #3a3a3a;
            }}
            QPushButton#B {{
                background: #1a1a1a;
                border: 1px solid {UI_EDGE};
                color: {UI_TXT};
                padding: 8px 14px;
                border-radius: 8px;
                font-weight: 800;
                min-width: 92px;
            }}
            QPushButton#B:hover {{
                background: #202020;
                border-color: #3a3a3a;
            }}
        """)

        lay = QtWidgets.QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        top = QtWidgets.QHBoxLayout()
        lab_t = QtWidgets.QLabel(title, objectName="T")
        btn_x = QtWidgets.QPushButton("×", objectName="X")
        btn_x.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_x.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        btn_x.clicked.connect(self.reject)
        top.addWidget(lab_t, 1)
        top.addWidget(btn_x, 0)
        lay.addLayout(top)

        lab_m = QtWidgets.QLabel(msg, objectName="M")
        lab_m.setWordWrap(True)
        lay.addWidget(lab_m, 1)

        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)

        # all buttons same grey (no white primary)
        for i, text in enumerate(buttons):
            b = QtWidgets.QPushButton(text, objectName="B")
            b.setFocusPolicy(QtCore.Qt.NoFocus)
            b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            b.clicked.connect(lambda _, ix=i: self._click(ix))
            row.addWidget(b)

        lay.addLayout(row)
        root.addWidget(frame)

        # drag anywhere
        self._dp = None
        frame.installEventFilter(self)

    def _click(self, idx: int):
        self._result = idx
        self.accept()

    def choice(self) -> int:
        return self._result

    def eventFilter(self, obj, ev):
        if ev.type() == QtCore.QEvent.MouseButtonPress and ev.button() == QtCore.Qt.LeftButton:
            self._dp = ev.globalPos() - self.frameGeometry().topLeft()
            return True
        if ev.type() == QtCore.QEvent.MouseMove and self._dp and (ev.buttons() & QtCore.Qt.LeftButton):
            self.move(ev.globalPos() - self._dp)
            return True
        if ev.type() == QtCore.QEvent.MouseButtonRelease:
            self._dp = None
            return True
        return False

def pop_info(parent, title, msg):
    StealthPopup(title, msg, "info", ("OK",), parent).exec_()

def pop_warn(parent, title, msg):
    StealthPopup(title, msg, "warn", ("OK",), parent).exec_()

def pop_error(parent, title, msg):
    StealthPopup(title, msg, "error", ("OK",), parent).exec_()

def pop_confirm(parent, title, msg, yes="Yes", no="No") -> bool:
    dlg = StealthPopup(title, msg, "confirm", (no, yes), parent)
    dlg.exec_()
    return dlg.choice() == 1

def pop_choice(parent, title, msg, *buttons: str) -> int:
    dlg = StealthPopup(title, msg, "confirm", buttons, parent)
    dlg.exec_()
    return dlg.choice()


class SettingsPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._feedback_window = None
        self._diagnostics_window = None
        self.setObjectName("SettingsRoot")
        self.setStyleSheet(self._qss())
        self._build_ui()
        self._load_app_settings()
        self._load_paths()

    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # ==========================================
        # SECTION 1: Game Configuration (Paths)
        # ==========================================
        config_frame = QtWidgets.QFrame()
        config_frame.setObjectName("Card")
        config_layout = QtWidgets.QVBoxLayout(config_frame)
        config_layout.setContentsMargins(16, 16, 16, 16)
        config_layout.setSpacing(12)

        lbl_config = QtWidgets.QLabel("Game Configuration")
        lbl_config.setObjectName("SectionTitle")

        # Bundle Input
        self.le_bundles = QtWidgets.QLineEdit()
        self.le_bundles.setReadOnly(True)
        self.le_bundles.setPlaceholderText("Path to AssetBundles folder...")
        btn_bundle = QtWidgets.QPushButton("Browse")
        btn_bundle.setObjectName("GhostBtn")
        btn_bundle.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_bundle.setCursor(QtCore.Qt.PointingHandCursor)
        btn_bundle.clicked.connect(self._pick_bundles)

        row_bundle = QtWidgets.QHBoxLayout()
        row_bundle.addWidget(self.le_bundles, 1)
        row_bundle.addWidget(btn_bundle, 0)

        # EXE Input
        self.le_gameexe = QtWidgets.QLineEdit()
        self.le_gameexe.setReadOnly(True)
        self.le_gameexe.setPlaceholderText("Path to Smash Legends.exe...")
        btn_game = QtWidgets.QPushButton("Browse")
        btn_game.setObjectName("GhostBtn")
        btn_game.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_game.setCursor(QtCore.Qt.PointingHandCursor)
        btn_game.clicked.connect(self._pick_gameexe)

        row_exe = QtWidgets.QHBoxLayout()
        row_exe.addWidget(self.le_gameexe, 1)
        row_exe.addWidget(btn_game, 0)

        # Auto Locate Button
        self.btn_auto = QtWidgets.QPushButton("Auto-locate Game Paths")
        self.btn_auto.setObjectName("ActionBtn")
        self.btn_auto.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_auto.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_auto.clicked.connect(self._auto_locate)

        config_layout.addWidget(lbl_config)
        config_layout.addWidget(QtWidgets.QLabel("AssetBundles Directory:", objectName="SubLabel"))
        config_layout.addLayout(row_bundle)
        config_layout.addWidget(QtWidgets.QLabel("Game Executable:", objectName="SubLabel"))
        config_layout.addLayout(row_exe)
        config_layout.addSpacing(5)
        config_layout.addWidget(self.btn_auto)

        # ==========================================
        # SECTION 2: Tools & Maintenance
        # ==========================================
        tools_frame = QtWidgets.QFrame()
        tools_frame.setObjectName("Card")
        tools_layout = QtWidgets.QVBoxLayout(tools_frame)
        tools_layout.setContentsMargins(16, 16, 16, 16)
        tools_layout.setSpacing(10)

        lbl_tools = QtWidgets.QLabel("Tools & Maintenance")
        lbl_tools.setObjectName("SectionTitle")

        # Restore
        self.btn_restore = QtWidgets.QPushButton("Restore Original Game Files")
        self.btn_restore.setObjectName("ToolBtn")
        self.btn_restore.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_restore.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_restore.setToolTip("Runs Steam file verification via steam_verification.bat")
        self.btn_restore.clicked.connect(self._restore_original_files)

        # Report Issue
        self.btn_issue = QtWidgets.QPushButton("Report an Issue")
        self.btn_issue.setObjectName("ToolBtn")
        self.btn_issue.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_issue.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_issue.clicked.connect(self._report_issue)

        # Diagnostics
        self.btn_diagnostics = QtWidgets.QPushButton("Run Mod Manager Diagnostics")
        self.btn_diagnostics.setObjectName("ToolBtn")
        self.btn_diagnostics.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_diagnostics.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_diagnostics.clicked.connect(self._open_diagnostics)

        tools_layout.addWidget(lbl_tools)
        tools_layout.addWidget(self.btn_restore)
        tools_layout.addWidget(self.btn_issue)
        tools_layout.addWidget(self.btn_diagnostics)

        # ==========================================
        # SECTION 3: App Preferences
        # ==========================================
        prefs_frame = QtWidgets.QFrame()
        prefs_frame.setObjectName("PlainSection")
        prefs_layout = QtWidgets.QVBoxLayout(prefs_frame)
        prefs_layout.setContentsMargins(0, 4, 0, 0)
        prefs_layout.setSpacing(8)

        lbl_prefs = QtWidgets.QLabel("App Preferences")
        lbl_prefs.setObjectName("PlainSectionTitle")

        self.cb_splash_intro = QtWidgets.QCheckBox("Show launch intro when starting the game")
        self.cb_splash_intro.setObjectName("ToggleOption")
        self.cb_splash_intro.setFocusPolicy(QtCore.Qt.NoFocus)
        self.cb_splash_intro.setCursor(QtCore.Qt.PointingHandCursor)
        self.cb_splash_intro.setChecked(False)
        self.cb_splash_intro.toggled.connect(self._save_app_settings)

        splash_note = QtWidgets.QLabel("Only plays when enabled and you press Launch Game.")
        splash_note.setObjectName("PlainSubLabel")

        prefs_layout.addWidget(lbl_prefs)
        prefs_layout.addWidget(self.cb_splash_intro)
        prefs_layout.addWidget(splash_note)

        main_layout.addWidget(config_frame)
        main_layout.addWidget(tools_frame)
        main_layout.addWidget(prefs_frame)
        main_layout.addStretch()

    # ---------- manual pickers ----------
    def _pick_bundles(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select AssetBundles folder", str(Path.home()))
        if path:
            p = Path(path)
            if p.exists() and p.is_dir():
                self.le_bundles.setText(str(p))
                self._save_paths()

    def _pick_gameexe(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select game.exe", str(Path.home()), "Executable (*.exe)")
        if path:
            p = Path(path)
            if p.exists() and p.is_file():
                self.le_gameexe.setText(str(p))
                self._save_paths()
    # -----------------------------------

    # ---------- Auto-locate (Steam) ----------
    def _auto_locate(self):
        game_dir = self._find_game_dir_from_steam(APPID)
        found_bundles: Optional[Path] = None
        found_exe: Optional[Path] = None

        if game_dir and game_dir.exists():
            exes = list(game_dir.glob("*.exe")) or list(game_dir.rglob("*.exe"))
            pref = [e for e in exes if any(h in e.name.lower() for h in GAME_HINTS)]
            found_exe = pref[0] if pref else (exes[0] if exes else None)

            data_dirs = list(game_dir.glob("*_Data"))
            if not data_dirs and exes:
                data_dirs = [p.parent for p in exes if p.parent.name.endswith("_Data")]
            for d in data_dirs:
                cand = d / "StreamingAssets" / "AssetBundles"
                if cand.exists() and cand.is_dir():
                    found_bundles = cand
                    break

        changed = False
        if found_bundles:
            self.le_bundles.setText(str(found_bundles))
            changed = True
        if found_exe:
            self.le_gameexe.setText(str(found_exe))
            changed = True
        if changed:
            self._save_paths()

        msg = [
            f"Game dir: {game_dir if game_dir else 'not found'}",
            f"game.exe: {found_exe if found_exe else 'not found'}",
            f"AssetBundles: {found_bundles if found_bundles else 'not found'}",
        ]
        pop_info(self, "Auto-locate", "\n".join(str(x) for x in msg))

    def _find_game_dir_from_steam(self, appid: int) -> Optional[Path]:
        steam_path = self._steam_root()
        if not steam_path:
            return None
        libs = self._steam_libraries(steam_path)
        if steam_path not in libs:
            libs.insert(0, steam_path)

        installdir: Optional[str] = None
        lib_for_app: Optional[Path] = None

        for lib in libs:
            man = lib / "steamapps" / f"appmanifest_{appid}.acf"
            if man.exists():
                installdir = self._parse_acf_value(man, "installdir")
                lib_for_app = lib
                break

        if not installdir or not lib_for_app:
            return None

        game_root = lib_for_app / "steamapps" / "common" / installdir
        if game_root.exists():
            return game_root

        guess = lib_for_app / "steamapps" / "common" / "Smash Legends"
        return guess if guess.exists() else None

    def _steam_root(self) -> Optional[Path]:
        try:
            import winreg  # type: ignore
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
                val, _ = winreg.QueryValueEx(k, "SteamPath")
                p = Path(val)
                if p.exists():
                    return p
        except Exception:
            pass

        candidates = [
            Path("C:/Program Files (x86)/Steam"),
            Path("C:/Program Files/Steam"),
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Steam",
            Path(os.environ.get("PROGRAMFILES", "")) / "Steam",
        ]
        for c in candidates:
            if c and c.exists():
                return c

        nx = Path.home() / ".steam" / "steam"
        if nx.exists():
            return nx
        mac = Path.home() / "Library" / "Application Support" / "Steam"
        if mac.exists():
            return mac
        return None

    def _steam_libraries(self, steam_root: Path) -> List[Path]:
        libs = [steam_root]
        vdf = steam_root / "steamapps" / "libraryfolders.vdf"
        if not vdf.exists():
            return libs
        try:
            text = vdf.read_text(encoding="utf-8", errors="ignore")
            paths = re.findall(r'"path"\s*"([^"]+)"', text, flags=re.IGNORECASE)
            for p in paths:
                pp = Path(p.replace("\\\\", "\\"))
                if pp.exists():
                    libs.append(pp)
        except Exception:
            pass

        out: List[Path] = []
        seen = set()
        for p in libs:
            s = str(p.resolve()).lower()
            if s not in seen:
                seen.add(s)
                out.append(p)
        return out

    def _parse_acf_value(self, acf_file: Path, key: str) -> Optional[str]:
        try:
            txt = acf_file.read_text(encoding="utf-8", errors="ignore")
            m = re.search(rf'"{re.escape(key)}"\s*"([^"]+)"', txt, flags=re.IGNORECASE)
            return m.group(1) if m else None
        except Exception:
            return None
    # ---------------------------------------

    # ---------- Common runner (same pipeline/flags) ----------
    def _run_bat(self, *, bat: Path, title: str, action_label: str, toast_text: str, show_confirm: bool = True):
        if not bat.exists():
            pop_warn(self, title, f"Script not found:\n{bat}\n\nMake sure it exists.")
            return

        if show_confirm:
            msg = (
                f"{action_label}\n"
                f"{'A new console will open.' if RESTORE_NEW_CONSOLE else 'Proceed with operation?'}\n"
            )
            if not pop_confirm(self, title, msg, yes="Yes", no="No"):
                return

        try:
            if os.name == "nt":
                if RESTORE_NEW_CONSOLE:
                    creation = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
                    subprocess.Popen(
                        ["cmd", "/k", str(bat)],
                        cwd=str(bat.parent),
                        creationflags=creation,
                        shell=False
                    )
                else:
                    creation = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                    proc = subprocess.Popen(
                        ["cmd", "/c", str(bat)],
                        cwd=str(bat.parent),
                        stdout=subprocess.PIPE if RESTORE_STREAM_TO_VSCODE else None,
                        stderr=subprocess.STDOUT if RESTORE_STREAM_TO_VSCODE else None,
                        creationflags=creation,
                        shell=False,
                        text=True, encoding="utf-8", errors="replace",
                    )
                    if RESTORE_STREAM_TO_VSCODE and proc.stdout is not None:
                        self._pump_stdout(proc.stdout, tag=title.lower().replace(" ", "_"))
            else:
                proc = subprocess.Popen(
                    ["bash", str(bat)],
                    cwd=str(bat.parent),
                    stdout=subprocess.PIPE if RESTORE_STREAM_TO_VSCODE else None,
                    stderr=subprocess.STDOUT if RESTORE_STREAM_TO_VSCODE else None,
                    shell=False,
                    text=True, encoding="utf-8", errors="replace",
                )
                if RESTORE_STREAM_TO_VSCODE and proc.stdout is not None:
                    self._pump_stdout(proc.stdout, tag=title.lower().replace(" ", "_"))

            if RESTORE_SHOW_POST_START_TOAST and show_confirm:
                pop_info(self, title, toast_text)
        except Exception as e:
            pop_error(self, title, f"Failed to start script:\n{e}")
    # ---------------------------------------------------------

    # ---------- Restore Original Files (Steam Verify) ----------
    def _resolve_smash_data_dir(self) -> Optional[Path]:
        game_exe_text = self.le_gameexe.text().strip()
        if game_exe_text:
            game_exe = Path(game_exe_text)
            candidate = game_exe.parent / "Smash_Legends_Data"
            if candidate.exists():
                return candidate

        bundles_text = self.le_bundles.text().strip()
        if bundles_text:
            bundles_dir = Path(bundles_text)
            candidate = bundles_dir.parent.parent
            if candidate.exists() and candidate.name.lower() == "smash_legends_data":
                return candidate

        game_dir = self._find_game_dir_from_steam(APPID)
        if game_dir and game_dir.exists():
            candidate = game_dir / "Smash_Legends_Data"
            if candidate.exists():
                return candidate

            for data_dir in game_dir.glob("*_Data"):
                if data_dir.is_dir():
                    return data_dir
        return None

    def _restore_original_files(self):
        mode = pop_choice(
            self,
            "Restore",
            "Choose how you want to restore the game files.\n\n"
            "Repair: run Steam file verification as-is.\n"
            "Clean Install: delete Smash_Legends_Data first, then run Steam verification.",
            "Cancel",
            "Repair",
            "Clean Install",
        )
        if mode == 0:
            return

        clean_install = mode == 2
        if clean_install:
            data_dir = self._resolve_smash_data_dir()
            if data_dir and data_dir.exists():
                try:
                    shutil.rmtree(data_dir)
                except Exception as e:
                    pop_error(self, "Restore", f"Failed to delete folder before repair:\n{data_dir}\n\n{e}")
                    return
            else:
                pop_info(
                    self,
                    "Restore",
                    "Smash_Legends_Data was not found, so the clean install step was skipped.\n\n"
                    "Steam verification will still run now.",
                )

        bat = PROJECT_ROOT / "source" / "xzen_engine" / "settings" / "steam_verification.bat"
        self._run_bat(
            bat=bat,
            title="Restore",
            action_label=(
                "Delete Smash_Legends_Data and run Steam file verification."
                if clean_install
                else "Run Steam file verification to restore original game files."
            ),
            toast_text="Steam verification started.",
            show_confirm=False,
        )

    # ---------- Report Issue (no popup; run instantly) ----------
    def _report_issue(self):
        try:
            if self._feedback_window is not None:
                try:
                    if self._feedback_window.isVisible():
                        self._feedback_window.show()
                        self._feedback_window.raise_()
                        self._feedback_window.activateWindow()
                        return
                except RuntimeError:
                    self._feedback_window = None

            module_path = BASE_DIR / "feedback.py"
            feedback_module = load_module_from_path("xzen_feedback", module_path)
            if feedback_module is None:
                raise FileNotFoundError(f"Feedback module was not found:\n{module_path}")

            feedback_cls = getattr(feedback_module, "FeedbackUI", None)
            if feedback_cls is None:
                raise AttributeError(f"Missing FeedbackUI in {module_path.name}")

            self._feedback_window = feedback_cls()
            self._feedback_window.destroyed.connect(lambda *_: setattr(self, "_feedback_window", None))
            self._feedback_window.show()
            self._feedback_window.raise_()
            self._feedback_window.activateWindow()
        except Exception as e:
            pop_error(self, "Report Issue", f"Failed to open feedback window:\n{e}")

    def _open_diagnostics(self):
        try:
            if self._diagnostics_window is not None:
                try:
                    if self._diagnostics_window.isVisible():
                        self._diagnostics_window.show()
                        self._diagnostics_window.raise_()
                        self._diagnostics_window.activateWindow()
                        return
                except RuntimeError:
                    self._diagnostics_window = None

            module_path = BASE_DIR / "diagnostics.py"
            diagnostics_module = load_module_from_path("xzen_diagnostics", module_path)
            if diagnostics_module is None:
                raise FileNotFoundError(f"Diagnostics module was not found:\n{module_path}")

            diagnostics_cls = getattr(diagnostics_module, "DiagnosticsUI", None)
            if diagnostics_cls is None:
                raise AttributeError(f"Missing DiagnosticsUI in {module_path.name}")

            self._diagnostics_window = diagnostics_cls()
            self._diagnostics_window.destroyed.connect(lambda *_: setattr(self, "_diagnostics_window", None))
            self._diagnostics_window.show()
            self._diagnostics_window.raise_()
            self._diagnostics_window.activateWindow()
        except Exception as e:
            pop_error(self, "Diagnostics", f"Failed to open diagnostics window:\n{e}")

    def _pump_stdout(self, stream: IO[str], tag: str = "proc") -> None:
        def _reader(s: IO[str]):
            try:
                for line in iter(s.readline, ""):
                    try:
                        sys.stdout.write(f"[{tag}] {line}")
                        sys.stdout.flush()
                    except Exception:
                        pass
            finally:
                try:
                    s.close()
                except Exception:
                    pass
        threading.Thread(target=_reader, args=(stream,), daemon=True).start()

    # ---------- persistence ----------
    def _load_app_settings(self):
        data = {}
        if APP_SETTINGS_JSON.exists():
            try:
                raw = json.loads(APP_SETTINGS_JSON.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    data = raw
            except Exception:
                data = {}
        self.cb_splash_intro.blockSignals(True)
        self.cb_splash_intro.setChecked(bool(data.get("show_splash_intro", False)))
        self.cb_splash_intro.blockSignals(False)

    def _save_app_settings(self):
        data = {}
        if APP_SETTINGS_JSON.exists():
            try:
                raw = json.loads(APP_SETTINGS_JSON.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    data = raw
            except Exception:
                data = {}
        data["show_splash_intro"] = self.cb_splash_intro.isChecked()
        try:
            APP_SETTINGS_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_paths(self):
        if PATHS_JSON.exists():
            try:
                raw_text = PATHS_JSON.read_text(encoding="utf-8")
                if not raw_text.strip():
                    return
                data = json.loads(raw_text)
                self.le_bundles.setText(str(data.get("assetbundles_dir", "")))
                self.le_gameexe.setText(str(data.get("game_exe", "")))
            except Exception as e:
                pop_error(self, "Paths Load Failed", f"Could not read:\n{PATHS_JSON}\n\n{e}")

    def _save_paths(self) -> bool:
        data = {
            "assetbundles_dir": self.le_bundles.text().strip(),
            "game_exe": self.le_gameexe.text().strip(),
        }
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            PATHS_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return True
        except Exception as e:
            pop_error(self, "Paths Save Failed", f"Could not write:\n{PATHS_JSON}\n\n{e}")
            return False
    # ----------------------------------

    def _qss(self) -> str:
        return f"""
        QWidget#SettingsRoot {{
            background: {BG_DARK};
            color: {TEXT};
            font-family: "Segoe UI", system-ui, sans-serif;
            font-size: 13px;
        }}

        QFrame#Card {{
            background-color: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 4px;
        }}

        QFrame#PlainSection {{
            background: transparent;
            border: none;
        }}

        QLabel#SectionTitle {{
            background: transparent;
            color: {TEXT};
            font-size: 16px;
            font-weight: 700;
            padding-bottom: 4px;
            border-bottom: 1px solid {BORDER};
        }}

        QLabel#SubLabel {{
            background: transparent;
            color: {TEXT_DIM};
            font-size: 12px;
            font-weight: 600;
        }}

        QLabel#PlainSectionTitle {{
            background: transparent;
            color: {TEXT};
            font-size: 15px;
            font-weight: 700;
        }}

        QLabel#PlainSubLabel {{
            background: transparent;
            color: {TEXT_DIM};
            font-size: 12px;
            font-weight: 600;
        }}

        QLineEdit {{
            background: #111111;
            color: {TEXT};
            border: 1px solid {BORDER};
            padding: 8px 10px;
            border-radius: 4px;
            font-family: "Consolas", monospace;
            font-size: 12px;
        }}
        QLineEdit:focus {{
            border: 1px solid {ACCENT};
        }}

        QPushButton#GhostBtn {{
            background: transparent;
            color: {TEXT_DIM};
            border: 1px solid {BORDER};
            padding: 7px 14px;
            border-radius: 4px;
            font-weight: 600;
        }}
        QPushButton#GhostBtn:hover {{
            background: #151515;
            color: {ACCENT};
            border: 1px solid {ACCENT};
        }}

        QPushButton#ActionBtn {{
            background-color: #eeeeee;
            color: #050505;
            border: none;
            padding: 10px 14px;
            border-radius: 4px;
            font-weight: 700;
        }}
        QPushButton#ActionBtn:hover {{
            background-color: #ffffff;
        }}

        QPushButton#ToolBtn {{
            background: transparent;
            color: {TEXT};
            border: 1px solid {BORDER};
            padding: 12px 16px;
            border-radius: 4px;
            font-weight: 600;
            text-align: left;
        }}
        QPushButton#ToolBtn:hover {{
            background-color: #111111;
            border: 1px solid {ACCENT};
        }}

        QCheckBox#ToggleOption {{
            background: transparent;
            color: {TEXT};
            spacing: 10px;
            font-weight: 600;
            padding: 2px 0;
        }}
        QCheckBox#ToggleOption::indicator {{
            width: 30px;
            height: 16px;
            border-radius: 8px;
            background-color: #252525;
            border: none;
        }}
        QCheckBox#ToggleOption::indicator:checked {{
            background-color: #eeeeee;
        }}
        QCheckBox#ToggleOption:hover {{
            color: {ACCENT};
        }}
        """
