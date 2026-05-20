import os, sys, json, shutil, subprocess, importlib.util, threading
import ctypes
from ctypes import wintypes
from typing import Dict, Optional, Tuple, List, IO
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve

# ===== DEBUG / BEHAVIOR SWITCHES =====
DEBUG_PIPE_TO_VSCODE = True
DEBUG_SHOW_CONSOLE   = False
# ====================================

# ======= EASY TWEAKS =======
WINDOW_W = 1070
WINDOW_H = 720
SPLASH_DURATION_MS = 3100
H_GAP, V_GAP = 12, 16
IMG_SIZE, LABEL_HEIGHT, BUTTON_HEIGHT = 150, 25, 30
ITEMS_PER_ROW = 5
INSERT_POPUP_OPACITY = 0.8
# ===========================

# ======= GLOBAL INSERT POPUP =======
HOTKEY_ID_INSERT_POPUP = 0xB100
WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
VK_INSERT = 0x2D
# ==================================

# ---------- EXE-safe app root ----------
def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(os.path.abspath(os.path.dirname(__file__)))
BASE_DIR = app_root()
# --------------------------------------

# Paths (project root)
BATS_DIR    = BASE_DIR / "source" / "xzen_engine" / "bats"
IMPORTS_DIR = BATS_DIR / "imports"                         # source/xzen_engine/bats/imports
UI_DIR      = BASE_DIR / "source" / "xzen_engine" / "ui"
STATE_DIR   = BASE_DIR / "source" / "profile" / "user_data"
STATE_JSON  = STATE_DIR / "btn_state.json"
ORDER_JSON  = STATE_DIR / "mod_ordering.json"
IMPORT_CONFIG_JSON = STATE_DIR / "import_config.json"      # import menu config
APP_SETTINGS_JSON = STATE_DIR / "app_settings.json"
PATHS_JSON = STATE_DIR / "paths.json"
LAUNCH_BAT  = BATS_DIR / "launch_game.bat"                 # launcher lives in bats/
ASSETS_DIR  = BASE_DIR / "source" / "xzen_engine" / "assets"
APP_ICON    = ASSETS_DIR / "xzen.ico"                      # app icon (.ico) path

LOCKED_IMPORTS = {
    "import emote mods.bat": "Import Emote Mods is temporarily locked because it is not working yet.",
}

# Dynamic Tab pages
PLUGINS_DIR = BASE_DIR / "source" / "xzen_engine" / "python"
IMPORT_HANDLERS_DIR = PLUGINS_DIR / "import_handlers"
def load_module_from_path(mod_name: str, file_path: Path):
    if not file_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(mod_name, str(file_path))
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod

xzen_library  = load_module_from_path("xzen_library",  PLUGINS_DIR / "library.py")      # \
xzen_settings = load_module_from_path("xzen_settings", PLUGINS_DIR / "settings.py")     # loads dynamic libraries of xzen tabs
xzen_downloads = load_module_from_path("xzen_downloads", PLUGINS_DIR / "downloads.py")
xzen_service = load_module_from_path("xzen_service", PLUGINS_DIR / "xzen_service.py")  # /
xzen_online_service = load_module_from_path("xzen_online_service", PLUGINS_DIR / "online_service.py")
xzen_github_mod_browser = load_module_from_path("xzen_github_mod_browser", PLUGINS_DIR / "github_mod_browser" / "browser.py")

IMPORT_HANDLER_SPECS = {
    "import skin mods.bat": ("import_skin_files.py", "open_import_skin_ui"),
    "import stage mods.bat": ("import_stage_files.py", "open_import_stage_ui"),
    "import icon mods.bat": ("import_ui_files.py", "open_import_skin_ui"),
}


def open_import_handler_for_bat(bat_path: Path):
    spec = IMPORT_HANDLER_SPECS.get(bat_path.name.lower())
    if not spec:
        return None

    handler_file, entry_name = spec
    module_path = IMPORT_HANDLERS_DIR / handler_file
    module = load_module_from_path(f"import_handler_{module_path.stem}", module_path)
    if module is None:
        raise FileNotFoundError(f"Import handler was not found:\n{module_path}")

    entry = getattr(module, entry_name, None)
    if not callable(entry):
        raise AttributeError(f"Missing import handler entry point '{entry_name}' in {module_path.name}")

    return entry()


# ===== Xzen Stealth Theme =====
ACCENT   = "#ffffff"   # High contrast white for active states
BG_DARK  = "#050505"   # Deepest black
PANEL    = "#0a0a0a"   # Slightly lighter black for panels
TEXT     = "#eeeeee"   # Off-white text
TEXT_DIM = "#888888"   # Dark grey text
BORDER   = "#333333"   # Subtle borders
ENABLE_CLR  = "#3CCB7F" # Keep functional green
DISABLE_CLR = "#FF6B6B" # Keep functional red
# =====================================

# Qt5/6 compat
QtAlignCenter   = getattr(QtCore.Qt, "AlignCenter",   getattr(QtCore.Qt.AlignmentFlag, "AlignCenter"))
QtAlignVCenter  = getattr(QtCore.Qt, "AlignVCenter",  getattr(QtCore.Qt.AlignmentFlag, "AlignVCenter"))
QtAlignTop      = getattr(QtCore.Qt, "AlignTop",      getattr(QtCore.Qt.AlignmentFlag, "AlignTop"))
QtScrollAsNeeded  = getattr(QtCore.Qt, "ScrollBarAsNeeded",  getattr(QtCore.Qt.ScrollBarPolicy, "ScrollBarAsNeeded"))
QtScrollAlwaysOff = getattr(QtCore.Qt, "ScrollBarAlwaysOff", getattr(QtCore.Qt.ScrollBarPolicy, "ScrollBarAlwaysOff"))
QtKeepAspectExpand = getattr(QtCore.Qt, "KeepAspectRatioByExpanding", getattr(QtCore.Qt.AspectRatioMode, "KeepAspectRatioByExpanding"))
QtSmoothTransform  = getattr(QtCore.Qt, "SmoothTransformation", getattr(QtCore.Qt.TransformationMode, "SmoothTransformation"))
QtWA_Hover   = getattr(QtCore.Qt, "WA_Hover", getattr(QtCore.Qt.WidgetAttribute, "WA_Hover"))
QtLeftButton = getattr(QtCore.Qt, "LeftButton", getattr(QtCore.Qt.MouseButton, "LeftButton"))
QtPointingHandCursor = getattr(QtCore.Qt, "PointingHandCursor", getattr(QtCore.Qt.CursorShape, "PointingHandCursor"))
QtNoFocus = getattr(QtCore.Qt, "NoFocus", getattr(QtCore.Qt.FocusPolicy, "NoFocus"))
QtFramelessWindowHint = getattr( QtCore.Qt, "FramelessWindowHint", getattr(QtCore.Qt.WindowType, "FramelessWindowHint"))
QtDialog = getattr( QtCore.Qt, "Dialog", getattr(QtCore.Qt.WindowType, "Dialog"))
QtWA_TranslucentBackground = getattr( QtCore.Qt, "WA_TranslucentBackground", getattr(QtCore.Qt.WidgetAttribute, "WA_TranslucentBackground"))
QtStrongFocus = getattr( QtCore.Qt, "StrongFocus", getattr(QtCore.Qt.FocusPolicy, "StrongFocus"))
QtNoItemFlags = getattr( QtCore.Qt, "NoItemFlags", getattr(QtCore.Qt.ItemFlag, "NoItemFlags"))
QtUserRole = getattr( QtCore.Qt, "UserRole", getattr(QtCore.Qt.ItemDataRole, "UserRole"))
QtFramelessWindowHint = getattr(QtCore.Qt, "FramelessWindowHint", getattr(QtCore.Qt.WindowType, "FramelessWindowHint"))
QtWindow = getattr(QtCore.Qt, "Window", getattr(QtCore.Qt.WindowType, "Window"))
QtWA_TranslucentBackground = getattr(QtCore.Qt, "WA_TranslucentBackground", getattr(QtCore.Qt.WidgetAttribute, "WA_TranslucentBackground"))
QtWindowStaysOnTopHint = getattr(QtCore.Qt, "WindowStaysOnTopHint", getattr(QtCore.Qt.WindowType, "WindowStaysOnTopHint"))

# ---- State management ----
def _ensure_dirs():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    BATS_DIR.mkdir(parents=True, exist_ok=True)
    IMPORTS_DIR.mkdir(parents=True, exist_ok=True)
    UI_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

def load_state() -> Dict[str, str]:
    _ensure_dirs()
    if STATE_JSON.exists():
        try:
            data = json.loads(STATE_JSON.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                out: Dict[str, str] = {}
                for k, v in data.items():
                    vv = str(v).strip().lower()
                    out[k] = "Disable" if vv in ("disable","disabled","false","0") else "Enable"
                return out
        except Exception:
            pass
    return {}

def load_state_snapshot() -> Tuple[Dict[str, str], bool]:
    _ensure_dirs()
    if not STATE_JSON.exists():
        return {}, False
    try:
        data = json.loads(STATE_JSON.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}, False
        out: Dict[str, str] = {}
        for k, v in data.items():
            vv = str(v).strip().lower()
            out[str(k)] = "Disable" if vv in ("disable", "disabled", "false", "0") else "Enable"
        return out, True
    except Exception:
        return {}, False

def load_order() -> Dict[str, int]:
    if not ORDER_JSON.exists():
        return {}
    try:
        raw = json.loads(ORDER_JSON.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        out: Dict[str, int] = {}
        for k, v in raw.items():
            try:
                out[str(k).strip().lower()] = int(v)
            except Exception:
                continue
        return out
    except Exception:
        return {}

def load_import_config() -> Dict[str, Dict]:
    """Load import menu configuration (order, display names, etc.)"""
    if not IMPORT_CONFIG_JSON.exists():
        return {}
    try:
        raw = json.loads(IMPORT_CONFIG_JSON.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        
        imports_list = raw.get("imports", [])
        if not isinstance(imports_list, list):
            return {}
        
        config_map: Dict[str, Dict] = {}
        for item in imports_list:
            if isinstance(item, dict) and "name" in item:
                name = item.get("name", "").lower()
                config_map[name] = item
        return config_map
    except Exception:
        return {}

def load_app_settings() -> Dict[str, object]:
    if not APP_SETTINGS_JSON.exists():
        return {}
    try:
        data = json.loads(APP_SETTINGS_JSON.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def splash_intro_enabled() -> bool:
    return bool(load_app_settings().get("show_splash_intro", False))


def load_paths_config() -> Dict[str, str]:
    if not PATHS_JSON.exists():
        return {}
    try:
        data = json.loads(PATHS_JSON.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def game_paths_need_setup() -> bool:
    data = load_paths_config()
    assetbundles_dir = str(data.get("assetbundles_dir", "")).strip()
    game_exe = str(data.get("game_exe", "")).strip()
    if not assetbundles_dir or not game_exe:
        return True
    if not Path(assetbundles_dir).is_dir():
        return True
    if not Path(game_exe).is_file():
        return True
    return False

def save_state(state: Dict[str, str]) -> None:
    _ensure_dirs()
    STATE_JSON.write_text(json.dumps(state, indent=2), encoding="utf-8")

def scan_pairs() -> Dict[str, Tuple[Optional[Path], Optional[Path], Optional[Path]]]: # -> keys: Enabe/Disable/Open bat paths


    items: Dict[str, Tuple[Optional[Path], Optional[Path], Optional[Path]]] = {} # keys -> ( can go into two states: enable/disable, or open-only )
    if not BATS_DIR.exists():
        return items

    for p in BATS_DIR.glob("*.bat"):
        n = p.name.lower()

        # ignore launcher (there's already a dedicated Launch Game button)
        if n == "launch_game.bat":
            continue

        if n.startswith("enable_") and n.endswith(".bat"):
            key = n[len("enable_"):-4]
            en, dis, op = items.get(key, (None, None, None))
            items[key] = (p, dis, op)

        elif n.startswith("disable_") and n.endswith(".bat"):
            key = n[len("disable_"):-4]
            en, dis, op = items.get(key, (None, None, None))
            items[key] = (en, p, op)


        elif n.startswith("open_") and n.endswith(".bat"):
            key = n[len("open_"):-4]
            en, dis, op = items.get(key, (None, None, None))
            items[key] = (en, dis, p)


    return items

def find_image_for_key(key: str) -> Optional[Path]:
    target = f"{key.lower()}.png"
    for p in UI_DIR.glob("*.png"):
        if p.name.lower() == target:
            return p
    return None

# ---- VS Code streaming helper ----
def _pump_stream(stream: IO[str], tag: str) -> None:
    try:
        for line in iter(stream.readline, ""):
            try:
                sys.stdout.write(f"[{tag}] {line}")
                sys.stdout.flush()
            except Exception:
                pass
    finally:
        try:
            stream.close()
        except Exception:
            pass

# ---- .bat execution (Windows), cwd to script folder ----
def open_bat(path: Path, wait: bool = False, show_console: bool = False, pipe_to_vscode: bool = False) -> int:
    """Return 0 if started (or finished ok when wait=True), else non-zero."""
    try:
        if sys.platform != "win32":
            return -998
        if not path.exists():
            return -997

        cmd_exe = os.environ.get("ComSpec", "cmd.exe")
        switch = "/k" if show_console else "/c"
        args = [cmd_exe, switch, str(path)]  # Python handles quoting

        if pipe_to_vscode and not show_console:
            proc = subprocess.Popen(
                args,
                cwd=str(path.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=0,
            )
            if proc.stdout is not None:
                threading.Thread(
                    target=_pump_stream, args=(proc.stdout, path.name), daemon=True
                ).start()
            return 0 if proc and proc.pid else -996

        creationflags = 0
        if show_console:
            creationflags |= getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
        else:
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

        if wait:
            return subprocess.call(args, cwd=str(path.parent), creationflags=creationflags)
        else:
            proc = subprocess.Popen(args, cwd=str(path.parent), creationflags=creationflags)
            return 0 if proc and proc.pid else -996
    except Exception as e:
        print("open_bat error:", e)
        return -999

# ---------- Custom Title Bar ----------
class TitleBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(38)
        self._drag_pos = None

        self.title = QtWidgets.QLabel("Xzen Mod Manager")
        self.title.setObjectName("titleText")

        self.btn_min = QtWidgets.QPushButton("–")
        self.btn_min.setObjectName("winBtn")
        self.btn_min.setFocusPolicy(QtNoFocus)
        self.btn_min.setCursor(QtGui.QCursor(QtPointingHandCursor))
        self.btn_min.clicked.connect(self._minimize)

        self.btn_close = QtWidgets.QPushButton("×")
        self.btn_close.setObjectName("winBtnClose")
        self.btn_close.setFocusPolicy(QtNoFocus)
        self.btn_close.setCursor(QtGui.QCursor(QtPointingHandCursor))
        self.btn_close.clicked.connect(self._close)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 8, 0)
        lay.setSpacing(8)
        lay.addWidget(self.title, 1)
        lay.addWidget(self.btn_min, 0)
        lay.addWidget(self.btn_close, 0)

    def _minimize(self):
        win = self.window()
        if win is not None:
            win.showMinimized()

    def _close(self):
        win = self.window()
        if win is not None:
            win.close()

    def mousePressEvent(self, a0: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if a0.button() == Qt.MouseButton.LeftButton:  # fixed constant
            win = self.window()
            if win is None:
                return
            self._drag_pos = a0.globalPos() - win.frameGeometry().topLeft()
            a0.accept()

    def mouseMoveEvent(self, a0: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if self._drag_pos is not None and (a0.buttons() & QtLeftButton):
            win = self.window()
            if win is None:
                return
            win.move(a0.globalPos() - self._drag_pos)
            a0.accept()

    def mouseReleaseEvent(self, a0: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        self._drag_pos = None
        a0.accept()

# ---------- Custom Import Dialog ----------
class ImportDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Scripts")
        self.setFixedSize(450, 400)
        self.setWindowFlags(QtFramelessWindowHint | QtDialog)
        self.setAttribute(QtWA_TranslucentBackground)

        self.selected_path = None
        self.default_open_text = "Select"

        # Main Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0,  0,  0,  0)

        # Background Frame
        self.frame = QtWidgets.QFrame()
        self.frame.setObjectName("DialogFrame")
        self.frame.setStyleSheet(f"""
            QFrame#DialogFrame {{
                background-color: {PANEL};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
        """)

        frame_layout = QtWidgets.QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(20, 20, 20, 20)
        frame_layout.setSpacing(15)

        # Title
        title = QtWidgets.QLabel("Select Script to Import")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT};")
        frame_layout.addWidget(title)

        # List Widget
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setFocusPolicy(QtStrongFocus)  # Needs focus for arrow keys (it was an idea to support keyboard navigation sideways for whatever reason)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {BG_DARK};
                border: 1px solid {BORDER};
                border-radius: 4px;
                color: {TEXT};
                padding: 5px;
                outline: 0;
            }}
            QListWidget::item {{
                padding: 10px;
                border-bottom: 1px solid #151515;
            }}
            QListWidget::item:selected {{
                background-color: #222;
                color: {ACCENT};
                border: 1px solid {ACCENT};
            }}
            QListWidget::item:focus {{
                border: none;
                outline: none;
            }}
        """)
        self.list_widget.itemDoubleClicked.connect(self.accept_selection)
        self.list_widget.itemSelectionChanged.connect(self.check_selection)
        frame_layout.addWidget(self.list_widget)

        # Populate List
        self.populate_list()

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()

        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_cancel.setCursor(QtPointingHandCursor)
        self.btn_cancel.setFocusPolicy(QtNoFocus)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_DIM}; border: 1px solid {BORDER};
                padding: 8px; border-radius: 4px; font-weight: 600;
            }}
            QPushButton:hover {{ color: {TEXT}; border-color: {TEXT}; }}
        """)

        self.btn_open = QtWidgets.QPushButton("Select")
        self.btn_open.setCursor(QtPointingHandCursor)
        self.btn_open.setFocusPolicy(QtNoFocus)
        self.btn_open.clicked.connect(self.accept_selection)
        self.btn_open.setEnabled(False)
        self.btn_open.setStyleSheet(f"""
            QPushButton {{
                background-color: {TEXT}; color: {BG_DARK}; border: none;
                padding: 8px; border-radius: 4px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #fff; }}
            QPushButton:disabled {{ background-color: #333; color: #555; }}
        """)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_open)
        frame_layout.addLayout(btn_layout)

        layout.addWidget(self.frame)

        # Add shadow
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QtGui.QColor(0, 0, 0, 150))
        self.frame.setGraphicsEffect(shadow)

    def populate_list(self):
        self.list_widget.clear()
        if not IMPORTS_DIR.exists():
            return

        bats = sorted(IMPORTS_DIR.glob("*.bat"))
        if not bats:
            item = QtWidgets.QListWidgetItem("No .bat files found in imports/")
            item.setFlags(QtNoItemFlags)
            self.list_widget.addItem(item)
            return

        # Load import config for custom ordering and display names // Ordering can be changed at user_data/mod_ordering.json
        import_config = load_import_config()
        
        # Create a list with order and display names
        bat_items = []
        for bat in bats:
            stem = bat.stem.lower()
            config = import_config.get(stem, {})
            order = config.get("order", 999)
            display_name = config.get("displayName", bat.stem)
            enabled = config.get("enabled", True)
            
            if enabled:
                bat_items.append((order, display_name, bat))
        
        # Sort by order value
        bat_items.sort(key=lambda x: x[0])
        
        # Add to list widget
        for order, display_name, bat in bat_items:
            lock_message = LOCKED_IMPORTS.get(bat.name.lower())
            item_text = f"🔒 {display_name}" if lock_message else display_name
            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(QtUserRole, str(bat))
            item.setData(QtUserRole + 1, bool(lock_message))
            item.setData(QtUserRole + 2, lock_message or "")
            self.list_widget.addItem(item)

    def check_selection(self):
        items = self.list_widget.selectedItems()
        if not items:
            self.btn_open.setEnabled(False)
            self.btn_open.setText(self.default_open_text)
            return

        selected = items[0]
        is_locked = bool(selected.data(QtUserRole + 1))
        self.btn_open.setEnabled(not is_locked)
        self.btn_open.setText("Locked" if is_locked else self.default_open_text)

    def accept_selection(self):
        items = self.list_widget.selectedItems()
        if items:
            selected = items[0]
            if bool(selected.data(QtUserRole + 1)):
                message = selected.data(QtUserRole + 2) or "This import is currently locked."
                QtWidgets.QMessageBox.information(self, "Locked", str(message))
                return
            self.selected_path = selected.data(QtUserRole)
            self.accept()

class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()

    def mousePressEvent(self, e: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if int(e.button()) == int(QtLeftButton):
            self.clicked.emit()
        super().mousePressEvent(e)

class ModItem(QtWidgets.QWidget):
    def __init__(
        self,
        feature_key: str,
        enable_path: Optional[Path],
        disable_path: Optional[Path],
        open_path: Optional[Path],
        state: Dict[str, str],
        on_state_changed,
        on_open_requested=None,
    ):
        super().__init__()
        self.feature_key = feature_key
        self.enable_path = enable_path
        self.disable_path = disable_path
        self.open_path = open_path
        self.state = state
        self.on_state_changed = on_state_changed
        self.on_open_requested = on_open_requested
        self._pix_source: Optional[QtGui.QPixmap] = None

        action_height = BUTTON_HEIGHT + 4
        self.setFixedSize(IMG_SIZE, IMG_SIZE + LABEL_HEIGHT + action_height + 14)
        self.setAttribute(QtWA_Hover, True)

        self.image_label = ClickableLabel()
        self.image_label.setFixedSize(IMG_SIZE, IMG_SIZE)
        self.image_label.setAlignment(QtAlignCenter)
        self.image_label.setCursor(QtGui.QCursor(QtPointingHandCursor))
        self.image_label.setStyleSheet(
            f"border: 1px solid {BORDER}; border-radius: 4px; background-color: #0b0b0b;"
        )
        self.image_label.clicked.connect(self._on_image_clicked)

        ip = find_image_for_key(feature_key)
        if ip and ip.exists():
            pm = QtGui.QPixmap(str(ip))
            if not pm.isNull():
                self._pix_source = pm
                self._apply_image()

        self.title_label = QtWidgets.QLabel(feature_key.replace("_", " ").title())
        self.title_label.setAlignment(QtAlignCenter)
        self.title_label.setFixedHeight(LABEL_HEIGHT)
        self.title_label.setStyleSheet(
            f"color: {TEXT}; font-weight: 600; font-size: 12px;"
        )

        # Decide button type:
        # - Open-only if open_path exists AND no enable/disable pair
        if self.open_path and not (self.enable_path or self.disable_path):
            self.btn = QtWidgets.QPushButton("Open")
        else:
            next_action = self.state.get(self.feature_key, "Enable")
            self.btn = QtWidgets.QPushButton(next_action if next_action in ("Enable", "Disable") else "Enable")

        self.btn.setFixedHeight(action_height)
        self.btn.setMinimumWidth(IMG_SIZE - 22)
        self.btn.setObjectName("modBtn")
        self.btn.setFocusPolicy(QtNoFocus)
        self.btn.setCursor(QtGui.QCursor(QtPointingHandCursor))
        self.btn.clicked.connect(self.on_click)
        self._apply_btn_style()
        self._update_btn_enabled()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self.image_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.btn)

    def _apply_image(self):
        if self._pix_source is None:
            return
        scaled = self._pix_source.scaled(
            IMG_SIZE, IMG_SIZE, QtKeepAspectExpand, QtSmoothTransform
        )
        x = max(0, (scaled.width() - IMG_SIZE) // 2)
        y = max(0, (scaled.height() - IMG_SIZE) // 2)
        self.image_label.setPixmap(
            scaled.copy(QtCore.QRect(x, y, IMG_SIZE, IMG_SIZE))
        )

    def _apply_btn_style(self):
        txt = self.btn.text()

        # Open-only uses "enable" visuals by default
        if txt == "Open":
            mode = "enable"
        else:
            mode = "enable" if txt == "Enable" else "disable"

        self.btn.setProperty("state", mode)
        accent = ENABLE_CLR if mode == "enable" else DISABLE_CLR
        fill = "rgba(60, 203, 127, 0.10)" if mode == "enable" else "rgba(255, 107, 107, 0.10)"
        fill_hover = "rgba(60, 203, 127, 0.20)" if mode == "enable" else "rgba(255, 107, 107, 0.20)"
        fill_press = "rgba(60, 203, 127, 0.28)" if mode == "enable" else "rgba(255, 107, 107, 0.28)"
        self.btn.setStyleSheet(
            f"""
            QPushButton {{
                color: {accent};
                background-color: {fill};
                border: 1px solid {accent};
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 800;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {fill_hover};
                border-color: {accent};
            }}
            QPushButton:pressed {{
                background-color: {fill_press};
            }}
            QPushButton:disabled {{
                color: #4d4d4d;
                border: 1px dashed #323232;
                background-color: rgba(255, 255, 255, 0.02);
            }}
            """
        )
        st = self.btn.style()
        if st is not None:
            st.unpolish(self.btn)
            st.polish(self.btn)
        self.btn.update()

    def enterEvent(self, a0: Optional[QtCore.QEvent]) -> None:  # type: ignore[override]
        super().enterEvent(a0)
        self.image_label.setStyleSheet(
            f"border: 1px solid {ACCENT}; border-radius: 4px; background-color: #1a1a1a;"
        )

    def leaveEvent(self, a0: Optional[QtCore.QEvent]) -> None:  # type: ignore[override]
        super().leaveEvent(a0)
        self.image_label.setStyleSheet(
            f"border: 1px solid {BORDER}; border-radius: 4px; background-color: #0b0b0b;"
        )

    def _update_btn_enabled(self):
        want = self.btn.text()

        if want == "Open":
            self.btn.setEnabled(self.open_path is not None)
            self.btn.setToolTip("" if self.open_path else "Missing open_*.bat")
            return

        if want == "Enable":
            self.btn.setEnabled(self.enable_path is not None)
            self.btn.setToolTip("" if self.enable_path else "Missing enable_*.bat")
        else:
            self.btn.setEnabled(self.disable_path is not None)
            self.btn.setToolTip("" if self.disable_path else "Missing disable_*.bat")

    def _on_image_clicked(self):
        if self.btn.isEnabled():
            self.on_click()

    def on_click(self):
        action = self.btn.text()

        # OPEN-only script
        if action == "Open":
            if not self.open_path:
                QtWidgets.QMessageBox.warning(self, "Missing script", f"No open_*.bat for '{self.feature_key}'.")
                return
            if callable(self.on_open_requested):
                try:
                    handled = bool(self.on_open_requested(self.feature_key, self.open_path))
                except Exception as e:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Open failed",
                        f"Could not open '{self.feature_key}'.\n\n{type(e).__name__}: {e}",
                    )
                    return
                if handled:
                    return
            rc = open_bat(
                self.open_path,
                wait=False,
                show_console=DEBUG_SHOW_CONSOLE,
                pipe_to_vscode=DEBUG_PIPE_TO_VSCODE,
            )
            if rc != 0:
                QtWidgets.QMessageBox.critical(self, "Script failed to start", f"{self.open_path.name} (code {rc}).")
                return
            return

        # TOGGLE script (Enable/Disable)
        path = self.enable_path if action == "Enable" else self.disable_path
        if not path:
            QtWidgets.QMessageBox.warning(
                self,
                "Missing script",
                f"No {action.lower()}_*.bat for '{self.feature_key}'.",
            )
            return

        rc = open_bat(
            path,
            wait=False,
            show_console=DEBUG_SHOW_CONSOLE,
            pipe_to_vscode=DEBUG_PIPE_TO_VSCODE,
        )
        if rc != 0:
            QtWidgets.QMessageBox.critical(
                self,
                "Script failed to start",
                f"{path.name} (code {rc}).",
            )
            return

        # toggle state updates 
        if action == "Enable" and self.disable_path:
            self.btn.setText("Disable")
            self.state[self.feature_key] = "Disable"
        elif action == "Disable" and self.enable_path:
            self.btn.setText("Enable")
            self.state[self.feature_key] = "Enable"
        else:
            self.state[self.feature_key] = action

        save_state(self.state)
        self._apply_btn_style()
        self._update_btn_enabled()
        if callable(self.on_state_changed):
            self.on_state_changed(self.feature_key, self.state[self.feature_key])

class DashboardPage(QtWidgets.QWidget):
    def __init__(self, on_open_requested=None):
        super().__init__()
        self.state = load_state()
        self.mod_items: Dict[str, ModItem] = {}
        self.order: List[str] = []
        self.row_widgets: List[QtWidgets.QWidget] = []
        self.import_windows: List[QtWidgets.QWidget] = []
        self.on_open_requested = on_open_requested

        header = QtWidgets.QLabel("Xzen Mod Manager")
        header.setObjectName("headerTitle")

        self.importBtn = QtWidgets.QPushButton("Import")
        self.importBtn.setObjectName("ghostBtn")
        self.importBtn.setFocusPolicy(QtNoFocus)
        self.importBtn.clicked.connect(self.open_import_dialog)

        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(16, 16, 16, 8)
        top.addWidget(header, 0, alignment=QtAlignTop)
        top.addStretch(1)
        top.addWidget(self.importBtn, 0, alignment=QtAlignTop)

        self.content_wrap = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content_wrap)
        self.content_layout.setContentsMargins(16, 16, 16, 16)
        self.content_layout.setSpacing(V_GAP)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidget(self.content_wrap)
        self.scroll.setWidgetResizable(True)
        self.scroll.setVerticalScrollBarPolicy(QtScrollAsNeeded)
        self.scroll.setHorizontalScrollBarPolicy(QtScrollAlwaysOff)
        self.scroll.setObjectName("scroll")
        self.scroll.setStyleSheet("border: none; background: transparent;")

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addLayout(top)
        root.addWidget(self.scroll)

        self.refresh_items()

    def _clear_content(self):
        for widget in self.row_widgets:
            widget.setParent(None)
        self.row_widgets.clear()
        while self.content_layout.count() > 0:
            item = self.content_layout.takeAt(0)
            if not item:
                continue
            w = item.widget()
            if w is not None:
                w.setParent(None)

    def _create_horizontal_layout(self):
        self._clear_content()
        if not self.order:
            empty = QtWidgets.QLabel("No .bat files found in source/xzen_engine/bats")
            empty.setAlignment(QtAlignCenter)
            empty.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 14px; padding: 40px;"
            )
            self.content_layout.addWidget(empty)
            return

        current_row_layout: Optional[QtWidgets.QHBoxLayout] = None
        current_row_widget: Optional[QtWidgets.QWidget] = None
        items_in_row = 0

        for key in self.order:
            if items_in_row == 0:
                current_row_widget = QtWidgets.QWidget()
                current_row_layout = QtWidgets.QHBoxLayout(current_row_widget)
                current_row_layout.setContentsMargins(0, 0, 0, 0)
                current_row_layout.setSpacing(H_GAP)
                self.row_widgets.append(current_row_widget)
                self.content_layout.addWidget(current_row_widget)
            assert current_row_layout is not None
            item = self.mod_items[key]
            current_row_layout.addWidget(item)
            items_in_row += 1
            if items_in_row >= ITEMS_PER_ROW:
                current_row_layout.addStretch()
                items_in_row = 0
        if items_in_row > 0 and current_row_layout is not None:
            current_row_layout.addStretch()
        self.content_layout.addStretch()

    def refresh_items(self):
        self.mod_items.clear()
        self.order = []
        pairs = scan_pairs()
        if not pairs:
            self._create_horizontal_layout()
            return

        order_map = load_order()
        INF = 10**9
        keys = list(pairs.keys())
        keys.sort(key=lambda k: (order_map.get(k.lower(), INF), k))

        for key in keys:
            en, dis, openp = pairs[key]

            # only store state for toggled ones
            if (en or dis) and key not in self.state:
                self.state[key] = "Enable"

            item = ModItem(
                key,
                en,
                dis,
                openp,
                self.state,
                self._on_state_changed,
                self.on_open_requested,
            )
            self.mod_items[key] = item
            self.order.append(key)

        save_state(self.state)
        self._create_horizontal_layout()

    def _on_state_changed(self, key: str, next_action: str):
        pass

    def open_import_dialog(self):
        _ensure_dirs()
        dialog = ImportDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            if dialog.selected_path:
                src = Path(dialog.selected_path)
                try:
                    import_ui = open_import_handler_for_bat(src)
                except Exception as e:
                    print(f"[import] internal handler failed for {src.name}: {e}")
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Import failed",
                        f"Could not open the import window for:\n{src.name}\n\n{type(e).__name__}: {e}",
                    )
                    return

                if import_ui is not None:
                    self.import_windows.append(import_ui)
                    import_ui.destroyed.connect(lambda *_args, ui=import_ui: self._forget_import_window(ui))
                    import_ui.raise_()
                    import_ui.activateWindow()
                    print(f"[import] opened internal handler for {src.name}")
                    return

                print(f"[import] openning {src} ...")
                rc = open_bat(
                    src,
                    wait=False,
                    show_console=DEBUG_SHOW_CONSOLE,
                    pipe_to_vscode=DEBUG_PIPE_TO_VSCODE,
                )
                if rc != 0:
                    print(f"[import] failed to start {src.name} (code {rc})")

    def _forget_import_window(self, ui: QtWidgets.QWidget):
        try:
            self.import_windows.remove(ui)
        except ValueError:
            pass

class Placeholder(QtWidgets.QWidget):
    def __init__(self, title: str):
        super().__init__()
        lbl = QtWidgets.QLabel(title + " - coming soon")
        lbl.setAlignment(QtAlignCenter)
        lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:14px;")
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(lbl)



class InsertPopupWindow(QtWidgets.QFrame):
    def __init__(self, owner=None):
        super().__init__(None)
        self.owner = owner
        self._drag_offset = None

        flags = QtWindow | QtCore.Qt.Tool | QtFramelessWindowHint
        try:
            flags |= QtCore.Qt.WindowStaysOnTopHint
        except Exception:
            pass
        self.setWindowFlags(flags)
        self.setAttribute(QtWA_TranslucentBackground, False)
        self.setWindowTitle("Quick Menu")
        self.setFixedSize(280, 198)
        self.setWindowOpacity(INSERT_POPUP_OPACITY)
        self.setObjectName("insertPopupRoot")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.title = QtWidgets.QLabel("Quick Menu")
        self.title.setObjectName("insertPopupTitle")
        self.title.setAlignment(QtAlignVCenter)

        self.desc = QtWidgets.QLabel("Insert closes")
        self.desc.setObjectName("insertPopupDesc")
        self.desc.setWordWrap(False)

        self.disable_btn = QtWidgets.QPushButton("Disable Mods")
        self.disable_btn.setObjectName("insertPopupActionBtn")
        self.disable_btn.setFocusPolicy(QtNoFocus)
        self.disable_btn.setCursor(QtGui.QCursor(QtPointingHandCursor))
        self.disable_btn.setFixedHeight(36)
        self.disable_btn.clicked.connect(self._disable_friend_mods)

        self.enable_btn = QtWidgets.QPushButton("Enable User Mods")
        self.enable_btn.setObjectName("insertPopupActionBtn")
        self.enable_btn.setFocusPolicy(QtNoFocus)
        self.enable_btn.setCursor(QtGui.QCursor(QtPointingHandCursor))
        self.enable_btn.setFixedHeight(36)
        self.enable_btn.clicked.connect(self._enable_user_mods)

        self.disable_local_btn = QtWidgets.QPushButton("Disable Local Mods")
        self.disable_local_btn.setObjectName("insertPopupActionBtn")
        self.disable_local_btn.setFocusPolicy(QtNoFocus)
        self.disable_local_btn.setCursor(QtGui.QCursor(QtPointingHandCursor))
        self.disable_local_btn.setFixedHeight(36)
        self.disable_local_btn.clicked.connect(self._disable_local_mods)

        self.friend_btn = QtWidgets.QPushButton("Friend List")
        self.friend_btn.setObjectName("insertPopupActionBtn")
        self.friend_btn.setFocusPolicy(QtNoFocus)
        self.friend_btn.setCursor(QtGui.QCursor(QtPointingHandCursor))
        self.friend_btn.setFixedHeight(34)
        self.friend_btn.clicked.connect(self._open_friend_list)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addWidget(self.title, 0)
        header.addStretch(1)
        header.addWidget(self.desc, 0)

        action_grid = QtWidgets.QGridLayout()
        action_grid.setContentsMargins(0, 0, 0, 0)
        action_grid.setHorizontalSpacing(8)
        action_grid.setVerticalSpacing(8)
        action_grid.addWidget(self.disable_btn, 0, 0)
        action_grid.addWidget(self.enable_btn, 0, 1)
        action_grid.addWidget(self.disable_local_btn, 1, 0)
        action_grid.addWidget(self.friend_btn, 1, 1)

        layout.addLayout(header)
        layout.addSpacing(2)
        layout.addLayout(action_grid)

        self.setStyleSheet(f"""
            QFrame#insertPopupRoot {{
                background: {PANEL};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
            QLabel#insertPopupTitle {{
                color: {TEXT};
                font-size: 13px;
                font-weight: 700;
                border: none;
                padding: 0;
                margin: 0;
            }}
            QLabel#insertPopupDesc {{
                color: {TEXT_DIM};
                font-size: 11px;
                border: none;
                padding: 0;
                margin: 0;
            }}
            QPushButton#insertPopupActionBtn {{
                background-color: #eeeeee;
                color: #050505;
                border: 1px solid #ffffff;
                border-radius: 4px;
                padding: 0 10px;
                min-height: 34px;
                max-height: 36px;
                font-weight: 800;
                font-size: 12px;
                text-align: center;
            }}
            QPushButton#insertPopupActionBtn:hover {{
                background-color: #ffffff;
            }}
            QPushButton#insertPopupActionBtn:pressed {{
                background-color: #dcdcdc;
            }}
        """)

    def _disable_friend_mods(self):
        if self.owner is not None:
            self.owner.disable_friend_mods()

    def _disable_local_mods(self):
        if self.owner is not None:
            self.owner.disable_local_mods_action()

    def _enable_user_mods(self):
        if self.owner is not None:
            self.owner.enable_local_user_mods()

    def _open_friend_list(self):
        if self.owner is not None:
            self.owner.open_service_window()

    def show_centered(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def mousePressEvent(self, event):
        if int(event.button()) == int(QtLeftButton):
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and (event.buttons() & QtLeftButton):
            self.move(event.globalPos() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        event.accept()
        super().mouseReleaseEvent(event)


class HotkeyFilter(QtCore.QAbstractNativeEventFilter):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def nativeEventFilter(self, eventType, message):
        if sys.platform == "win32" and eventType == "windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and int(msg.wParam) == HOTKEY_ID_INSERT_POPUP:
                if self.owner is not None:
                    self.owner.toggle_insert_popup()
                return True, 0
        return False, 0



class ServiceWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__(None)
        self.setWindowTitle("Friendlist")
        self.setMinimumSize(900, 620)
        try:
            if APP_ICON.exists():
                self.setWindowIcon(QtGui.QIcon(str(APP_ICON)))
        except Exception:
            pass

        if xzen_service and hasattr(xzen_service, "ServicePage"):
            try:
                page = xzen_service.ServicePage()
            except Exception as e:
                page = Placeholder(f"Friendlist failed to load: {e}")
        else:
            page = Placeholder("Friendlist")

        self.setCentralWidget(page)
        self.setStyleSheet(f"QMainWindow {{ background:{BG_DARK}; color:{TEXT}; }}")


class SplashIntro(QtWidgets.QWidget):
    finished = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__(None)
        self._done = False

        self.setWindowFlags(QtFramelessWindowHint | QtWindow | QtWindowStaysOnTopHint)
        self.setAttribute(QtWA_TranslucentBackground, False)
        self.setFocusPolicy(QtStrongFocus)
        self.setWindowTitle("Xzen Mod Manager")

        try:
            if APP_ICON.exists():
                self.setWindowIcon(QtGui.QIcon(str(APP_ICON)))
        except Exception:
            pass

        self._build_ui()
        self._setup_animations()

        self.status_timer = QtCore.QTimer(self)
        self.status_timer.timeout.connect(self._sync_status_text)

    def _build_ui(self):
        self.setObjectName("splashRoot")

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(64, 48, 64, 48)
        root.setSpacing(0)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(12)

        self.top_mark = QtWidgets.QLabel("XZEN")
        self.top_mark.setObjectName("splashTopMark")
        self.top_status = QtWidgets.QLabel("MOD MANAGER")
        self.top_status.setObjectName("splashTopStatus")
        top.addWidget(self.top_mark, 0)
        top.addWidget(self.top_status, 0)
        top.addStretch(1)
        root.addLayout(top)

        center = QtWidgets.QVBoxLayout()
        center.setSpacing(16)

        self.logo = QtWidgets.QLabel()
        self.logo.setObjectName("splashLogo")
        self.logo.setAlignment(QtAlignCenter)
        self.logo.setFixedSize(112, 112)
        icon_pix = QtGui.QPixmap()
        try:
            if APP_ICON.exists():
                icon_pix = QtGui.QIcon(str(APP_ICON)).pixmap(96, 96)
        except Exception:
            icon_pix = QtGui.QPixmap()
        if not icon_pix.isNull():
            self.logo.setPixmap(icon_pix)
        else:
            self.logo.setText("X")

        self.title = QtWidgets.QLabel("XZEN MOD MANAGER")
        self.title.setObjectName("splashTitle")
        self.title.setAlignment(QtAlignCenter)

        self.subtitle = QtWidgets.QLabel("Initializing mod engine")
        self.subtitle.setObjectName("splashSubtitle")
        self.subtitle.setAlignment(QtAlignCenter)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setObjectName("splashProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setMinimumWidth(260)
        self.progress.setMaximumWidth(520)
        self.progress.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.status = QtWidgets.QLabel("Preparing workspace...")
        self.status.setObjectName("splashStatus")
        self.status.setAlignment(QtAlignCenter)

        center.addStretch(1)
        center.addWidget(self.logo, 0, alignment=QtAlignCenter)
        center.addWidget(self.title, 0, alignment=QtAlignCenter)
        center.addWidget(self.subtitle, 0, alignment=QtAlignCenter)
        center.addSpacing(14)
        center.addWidget(self.progress, 0, alignment=QtAlignCenter)
        center.addWidget(self.status, 0, alignment=QtAlignCenter)
        center.addStretch(1)
        root.addLayout(center, 1)

        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch(1)
        self.bottom_status = QtWidgets.QLabel("Configs Ready")
        self.bottom_status.setObjectName("splashBottomStatus")
        bottom.addWidget(self.bottom_status)
        root.addLayout(bottom)

        self.setStyleSheet(f"""
            QWidget#splashRoot {{
                background-color: {BG_DARK};
                color: {TEXT};
                font-family: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont;
            }}
            QLabel#splashTopMark {{
                color: {TEXT};
                font-size: 13px;
                font-weight: 900;
                letter-spacing: 0;
            }}
            QLabel#splashTopStatus, QLabel#splashBottomStatus {{
                color: {TEXT_DIM};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0;
            }}
            QLabel#splashLogo {{
                color: {TEXT};
                background-color: {BG_DARK};
                border: none;
                font-size: 48px;
                font-weight: 900;
            }}
            QLabel#splashTitle {{
                color: {TEXT};
                font-size: 34px;
                font-weight: 900;
                letter-spacing: 0;
            }}
            QLabel#splashSubtitle {{
                color: {TEXT_DIM};
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#splashStatus {{
                color: #bbbbbb;
                font-size: 12px;
                font-weight: 600;
            }}
            QProgressBar#splashProgress {{
                background-color: #151515;
                border: 1px solid {BORDER};
                border-radius: 4px;
            }}
            QProgressBar#splashProgress::chunk {{
                background-color: {TEXT};
                border-radius: 3px;
            }}
        """)

    def _setup_animations(self):
        self.progress_anim = QPropertyAnimation(self.progress, b"value")
        self.progress_anim.setDuration(SPLASH_DURATION_MS)
        self.progress_anim.setStartValue(0)
        self.progress_anim.setEndValue(100)
        self.progress_anim.setEasingCurve(QEasingCurve.InOutCubic)
        self.progress_anim.finished.connect(self._finish)

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, "_started"):
            self._started = True
            self.progress_anim.start()
            self.status_timer.start(70)

    def _sync_status_text(self):
        progress = self.progress.value()
        if progress < 28:
            self.status.setText("Preparing workspace...")
        elif progress < 58:
            self.status.setText("Loading core systems...")
        elif progress < 86:
            self.status.setText("Syncing interface...")
        else:
            self.status.setText("Ready.")

    def _finish(self):
        if self._done:
            return
        self._done = True
        self.status_timer.stop()
        self.progress_anim.stop()
        self.progress.setValue(100)
        self.status.setText("Ready.")
        self.finished.emit()

    def mousePressEvent(self, event):
        if int(event.button()) == int(QtLeftButton):
            self._finish()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Escape, QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Space):
            self._finish()
            event.accept()
            return
        super().keyPressEvent(event)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        # Frameless window to draw our title bar
        self.setWindowFlags(QtFramelessWindowHint | QtWindow)
        self.setAttribute(QtWA_TranslucentBackground, False)
        
        # sets initial opacity to 0 for fade-in effect
        self.setWindowOpacity(0.0)


        # Set window icon from assets if available otherwise output a message
        try:
            if APP_ICON.exists():
                self.setWindowIcon(QtGui.QIcon(str(APP_ICON)))
            else:
                print(f"[icon] APP_ICON not found at: {APP_ICON}")
        except Exception as e:
            print(f"[icon] failed to set app icon: {e}")

        self.setFixedSize(WINDOW_W, WINDOW_H)

        self.insert_popup = InsertPopupWindow(self)
        self.service_window = None
        self.hotkey_filter = None
        self._insert_hotkey_registered = False
        self.launch_splash = None
        self._path_setup_prompted = False
        self.ui_mod_windows: List[QtWidgets.QWidget] = []

        # Sidebar
        self.nav = QtWidgets.QListWidget()
        for item in ("Dashboard", "Library", "Plugins", "Friendlist", "Community Mods", "Share Mods", "Settings"):
            QtWidgets.QListWidgetItem(item, self.nav)
        self.nav.setCurrentRow(0)
        self.nav.setObjectName("nav")
        self.nav.setFocusPolicy(QtNoFocus)

        self.launchBtn = QtWidgets.QPushButton("Launch Game")
        self.launchBtn.setObjectName("launchBtn")
        self.launchBtn.clicked.connect(self.launch_game)
        self.launchBtn.setFocusPolicy(QtNoFocus)

        self.side = QtWidgets.QFrame()
        self.side.setObjectName("side")
        sideLay = QtWidgets.QVBoxLayout(self.side)
        sideLay.setContentsMargins(0, 0, 0, 0)
        sideLay.setSpacing(8)
        sideLay.addWidget(self.nav, 1)
        sideLay.addStretch(0)
        pad = QtWidgets.QWidget()
        padLay = QtWidgets.QHBoxLayout(pad)
        padLay.setContentsMargins(8, 8, 8, 8)
        padLay.addWidget(self.launchBtn)
        sideLay.addWidget(pad, 0)

        # Pages
        self.pages = QtWidgets.QStackedWidget()
        self.page_dashboard = DashboardPage(self._handle_dashboard_open_request)
        self.page_library = (
            xzen_library.LibraryPage()
            if xzen_library and hasattr(xzen_library, "LibraryPage")
            else Placeholder("Library")
        )
        
        self.page_downloads = (
            xzen_downloads.DownloadsPage()
            if xzen_downloads and hasattr(xzen_downloads, "DownloadsPage")
            else Placeholder("Downloads")
        )
        self.page_service = (
            xzen_service.ServicePage()
            if xzen_service and hasattr(xzen_service, "ServicePage")
            else Placeholder("Friendlist")
        )
        self.page_github_mod_browser = (
            xzen_github_mod_browser.GitHubModsPage()
            if xzen_github_mod_browser and hasattr(xzen_github_mod_browser, "GitHubModsPage")
            else Placeholder("Community Mods")
        )
        self.page_online_service = (
            xzen_online_service.OnlineServicePage()
            if xzen_online_service and hasattr(xzen_online_service, "OnlineServicePage")
            else Placeholder("Share Mods")
        )

        self.page_settings = (
            xzen_settings.SettingsPage()
            if xzen_settings and hasattr(xzen_settings, "SettingsPage")
            else Placeholder("Settings")
        )
        self.pages.addWidget(self.page_dashboard)
        self.pages.addWidget(self.page_library)
        self.pages.addWidget(self.page_downloads)
        self.pages.addWidget(self.page_service)
        self.pages.addWidget(self.page_github_mod_browser)
        self.pages.addWidget(self.page_online_service)
        self.pages.addWidget(self.page_settings)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)

        # Custom title bar
        self.titlebar = TitleBar(self)

        # Central root
        center = QtWidgets.QWidget()
        center.setObjectName("root")

        outer = QtWidgets.QVBoxLayout(center)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.titlebar, 0)

        body = QtWidgets.QWidget()
        body.setObjectName("body")
        bodyLay = QtWidgets.QHBoxLayout(body)
        bodyLay.setContentsMargins(0, 0, 0, 0)
        bodyLay.setSpacing(0)
        bodyLay.addWidget(self.side, 0)
        bodyLay.addWidget(self.pages, 1)

        outer.addWidget(body, 1)

        self.setCentralWidget(center)
        self.setStyleSheet(self._qss())
        
        # Startup animation
        self._setup_startup_animation()
        self._register_insert_hotkey()


    def _handle_dashboard_open_request(self, feature_key: str, open_path: Path) -> bool:
        if open_path.name.lower() != "open_ui_mods.bat":
            return False
        self.open_ui_mods_panel_internal()
        return True

    def open_ui_mods_panel_internal(self):
        module_path = PLUGINS_DIR / "UI_Mods_Panel.py"
        module = load_module_from_path("xzen_ui_mods_panel", module_path)
        if module is None:
            raise FileNotFoundError(f"UI Mods panel was not found:\n{module_path}")

        entry = getattr(module, "open_ui_mods_panel", None)
        if not callable(entry):
            raise AttributeError(f"Missing UI Mods entry point 'open_ui_mods_panel' in {module_path.name}")

        panel = entry()
        if panel is None:
            raise RuntimeError("UI Mods panel did not return a window instance.")

        self.ui_mod_windows.append(panel)
        panel.destroyed.connect(lambda *_args, ui=panel: self._forget_ui_mod_window(ui))
        panel.raise_()
        panel.activateWindow()

    def _forget_ui_mod_window(self, ui: QtWidgets.QWidget):
        try:
            self.ui_mod_windows.remove(ui)
        except ValueError:
            pass

    def _register_insert_hotkey(self):
        if sys.platform != "win32":
            print("[hotkey] global Insert hotkey only implemented for Windows.")
            return
        try:
            user32 = ctypes.windll.user32
            if not user32.RegisterHotKey(None, HOTKEY_ID_INSERT_POPUP, MOD_NOREPEAT, VK_INSERT):
                print("[hotkey] failed to register Insert hotkey.")
                return
            self.hotkey_filter = HotkeyFilter(self)
            QtWidgets.QApplication.instance().installNativeEventFilter(self.hotkey_filter)
            self._insert_hotkey_registered = True
        except Exception as e:
            print(f"[hotkey] register failed: {e}")

    def _unregister_insert_hotkey(self):
        if sys.platform != "win32":
            return
        try:
            if self.hotkey_filter is not None:
                QtWidgets.QApplication.instance().removeNativeEventFilter(self.hotkey_filter)
                self.hotkey_filter = None
        except Exception:
            pass
        try:
            if self._insert_hotkey_registered:
                ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID_INSERT_POPUP)
                self._insert_hotkey_registered = False
        except Exception as e:
            print(f"[hotkey] unregister failed: {e}")

    def toggle_insert_popup(self):
        if self.insert_popup.isVisible():
            self.insert_popup.hide()
        else:
            self.insert_popup.show_centered()

    def _disable_local_mods(self) -> Tuple[bool, str]:
        pairs = scan_pairs()
        disabled_any = False
        failed = []
        state, state_loaded = load_state_snapshot()
        toggle_keys = [key for key, (en_path, dis_path, _) in pairs.items() if en_path or dis_path]
        knows_all_toggle_states = state_loaded and all(key in state for key in toggle_keys)

        if knows_all_toggle_states:
            target_keys = [key for key in toggle_keys if state.get(key) == "Disable"]
        else:
            target_keys = toggle_keys

        for key in target_keys:
            _, dis_path, _ = pairs.get(key, (None, None, None))
            if not dis_path:
                continue
            rc = open_bat(
                dis_path,
                wait=False,
                show_console=DEBUG_SHOW_CONSOLE,
                pipe_to_vscode=DEBUG_PIPE_TO_VSCODE,
            )
            if rc == 0:
                disabled_any = True
            else:
                failed.append(f"{key}: {dis_path.name}")

        if not state_loaded:
            state = load_state()
        for key in target_keys:
            en_path, dis_path, _ = pairs.get(key, (None, None, None))
            if en_path or dis_path:
                state[key] = "Enable"
        save_state(state)

        try:
            if hasattr(self, "page_dashboard") and self.page_dashboard is not None:
                self.page_dashboard.state = state
                self.page_dashboard.refresh_items()
        except Exception:
            pass

        if failed:
            return False, "Some disable scripts failed to start:\n" + "\n".join(failed)
        if knows_all_toggle_states and not target_keys:
            return False, "No known local mods are currently enabled."
        if disabled_any:
            if knows_all_toggle_states:
                return True, "Started disable scripts only for the local mods that were marked enabled."
            return True, "Started all available local disable scripts because the saved mod state was incomplete."
        return False, "No local disable_*.bat files were found."

    def enable_local_user_mods(self):
        pairs = scan_pairs()
        target_keys = ("skins", "emotes")
        enabled_any = False
        failed = []

        for key in target_keys:
            enable_path, _, _ = pairs.get(key, (None, None, None))
            if not enable_path:
                failed.append(f"{key}: missing enable script")
                continue

            rc = open_bat(
                enable_path,
                wait=False,
                show_console=DEBUG_SHOW_CONSOLE,
                pipe_to_vscode=DEBUG_PIPE_TO_VSCODE,
            )
            if rc == 0:
                enabled_any = True
            else:
                failed.append(f"{key}: {enable_path.name} (code {rc})")

        state = load_state()
        for key in target_keys:
            enable_path, disable_path, _ = pairs.get(key, (None, None, None))
            if enable_path or disable_path:
                state[key] = "Disable"
        save_state(state)

        try:
            if hasattr(self, "page_dashboard") and self.page_dashboard is not None:
                self.page_dashboard.state = state
                self.page_dashboard.refresh_items()
        except Exception:
            pass

        if failed and not enabled_any:
            QtWidgets.QMessageBox.warning(
                self.insert_popup,
                "Enable User Mods",
                "Could not enable the local skin/emote mods.\n\n" + "\n".join(failed),
            )
            return

        if failed:
            QtWidgets.QMessageBox.warning(
                self.insert_popup,
                "Enable User Mods",
                "Enabled the available local skin/emote mods, but some entries had issues.\n\n" + "\n".join(failed),
            )
            return

        if enabled_any:
            QtWidgets.QMessageBox.information(
                self.insert_popup,
                "Enable User Mods",
                "Started the local skin and emote enable scripts.\n\nFriendlist profile mods were not changed.",
            )
            return

        QtWidgets.QMessageBox.warning(
            self.insert_popup,
            "Enable User Mods",
            "No local skin or emote enable scripts were found.",
        )

    def _disable_online_profile_mods(self) -> Tuple[bool, str]:
        if xzen_service is None:
            return False, "Friendlist service is not available."
        if not hasattr(xzen_service, "active_online_runtime_mods") or not hasattr(xzen_service, "disable_all_active_online_mods"):
            return False, "Friendlist online disable helpers are not available."

        active_mods = xzen_service.active_online_runtime_mods()
        if not isinstance(active_mods, list) or not active_mods:
            return False, ""

        restored_mods = xzen_service.disable_all_active_online_mods()
        restored_mods = [item for item in restored_mods if isinstance(item, dict)]
        if not restored_mods:
            return False, ""
        titles = [str(item.get("mod_title", "")).strip() for item in restored_mods if str(item.get("mod_title", "")).strip()]
        if not titles:
            return True, f"Disabled {len(restored_mods)} loaded Friendlist mod(s)."
        return True, f"Disabled loaded Friendlist mod(s): {', '.join(titles)}."

    def disable_friend_mods(self):
        try:
            online_disabled, online_message = self._disable_online_profile_mods()
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self.insert_popup,
                "Disable Mods",
                f"Could not disable the loaded Friendlist profile.\n\n{e}",
            )
            return

        if online_disabled:
            self.launch_game()
            return

        QtWidgets.QMessageBox.warning(
            self.insert_popup,
            "Disable Mods",
            "No loaded Friendlist modpacks are currently active.",
        )

    def disable_local_mods_action(self):
        local_disabled, local_message = self._disable_local_mods()
        if local_disabled:
            self.launch_game()
            return

        if local_message:
            QtWidgets.QMessageBox.warning(
                self.insert_popup,
                "Disable Local Mods",
                local_message,
            )

    def open_service_window(self):
        try:
            if self.service_window is None:
                self.service_window = ServiceWindow()
            self.service_window.show()
            self.service_window.raise_()
            self.service_window.activateWindow()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.insert_popup, "Friend List", f"Failed to open friend list window.\n\n{e}")

    def closeEvent(self, event):
        try:
            if self.insert_popup is not None:
                self.insert_popup.close()
            if self.service_window is not None:
                self.service_window.close()
        finally:
            self._unregister_insert_hotkey()
            super().closeEvent(event)

    def _setup_startup_animation(self):
        # Fade-in animation
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(200)  # 500ms fade-in
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)

    def _play_startup_animation(self):
        if hasattr(self, 'fade_anim'):
            self.fade_anim.start()

    def _prompt_for_game_path_setup(self):
        if self._path_setup_prompted:
            return
        self._path_setup_prompted = True

        if not game_paths_need_setup():
            return

        self.nav.setCurrentRow(6)

        settings_page = getattr(self, "page_settings", None)
        auto_button = getattr(settings_page, "btn_auto", None)
        if isinstance(auto_button, QtWidgets.QPushButton):
            auto_button.setFocus(QtCore.Qt.OtherFocusReason)

        popup = getattr(xzen_settings, "pop_info", None)
        message = (
            "Game paths are not configured yet, or the saved game path no longer exists.\n\n"
            "Open Settings and press Auto-locate Game Paths before using the manager."
        )
        if callable(popup):
            popup(self, "Set Game Paths", message)
            return

        QtWidgets.QMessageBox.information(self, "Set Game Paths", message)

    def showEvent(self, event):

        super().showEvent(event)
        # Play animation on first show
        if not hasattr(self, '_animation_played'):
            self._animation_played = True
            self._play_startup_animation()
            QtCore.QTimer.singleShot(0, self._prompt_for_game_path_setup)

    def _start_game_launch(self):
        path = LAUNCH_BAT
        rc = open_bat(
            path,
            wait=False,
            show_console=DEBUG_SHOW_CONSOLE,
            pipe_to_vscode=DEBUG_PIPE_TO_VSCODE,
        )
        if rc != 0:
            QtWidgets.QMessageBox.critical(
                self,
                "Launch failed to start",
                f"{path.name} (code {rc}).",
            )

    def _show_launch_intro(self):
        if self.launch_splash is not None and self.launch_splash.isVisible():
            self.launch_splash.raise_()
            self.launch_splash.activateWindow()
            return

        splash = SplashIntro()
        self.launch_splash = splash
        splash.title.setText("LAUNCHING GAME")
        splash.subtitle.setText("Preparing Smash Legends")
        splash.status.setText("Starting game...")
        splash.bottom_status.setText("Game Launch")
        launch_started = False

        def finish_launch():
            if self.launch_splash is splash:
                self.launch_splash = None
            splash.close()

        def start_launch_once():
            nonlocal launch_started
            if launch_started:
                return
            launch_started = True
            self._start_game_launch()

        splash.finished.connect(finish_launch)
        splash.destroyed.connect(lambda *_: setattr(self, "launch_splash", None) if self.launch_splash is splash else None)
        splash.showFullScreen()
        splash.raise_()
        splash.activateWindow()
        QtCore.QTimer.singleShot(0, start_launch_once)

    def launch_game(self):
        path = LAUNCH_BAT
        if not path.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "Missing launcher",
                f"'{path.name}' not found.\nExpected here:\n{path}\n\nPut it into:\n{BATS_DIR}",
            )
            return

        if splash_intro_enabled():
            self._show_launch_intro()
            return

        self._start_game_launch()

    def _qss(self) -> str:
        return f"""
        /* GLOBAL: kill dotted focus */
        * {{outline: none;}}
        QPushButton:focus, QListWidget:focus {{outline: none;}}
        QWidget {{background:{BG_DARK}; color:{TEXT}; font-family: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont; font-size:13px;}}
        QWidget#root {{ background-color: {BG_DARK}; border: none;}}

        /* Title bar */
        QWidget#titleBar {{ background-color: {PANEL}; border-bottom: 1px solid {BORDER};}}
        QLabel#titleText {{ color: {TEXT}; font-weight: 700; font-size: 12px; letter-spacing: 0.4px;}}
        QPushButton#winBtn {{ background: transparent; border: 1px solid {BORDER}; color: {TEXT}; min-width: 34px; max-width: 34px; min-height: 24px; max-height: 24px; border-radius: 4px; border-color: {ACCENT}; background: #111;}}
        QPushButton#winBtnClose {{ background: transparent; border: 1px solid {BORDER}; color: {TEXT}; min-width: 34px; max-width: 34px; min-height: 24px; max-height: 24px; border-radius: 4px; font-weight: 900;}}
        QPushButton#winBtnClose:hover {{ border-color: {DISABLE_CLR}; background: rgba(255,107,107,0.12);}}

        /* Sidebar */
        #side {{ background-color: {PANEL}; border-right: 1px solid {BORDER}; min-width:220px; max-width:240px;}}
        #nav {{ background: transparent; padding: 8px 0; border: none;}}

        QListWidget::item {{ padding: 10px 14px; margin: 4px 8px; border-radius: 4px; color: {TEXT_DIM}; border: 1px solid transparent;}}
        QListWidget::item:selected {{ background-color: #1a1a1a; color: {ACCENT}; border: 1px solid {BORDER}; font-weight: 600;}}
        QListWidget::item:hover:!selected {{ background-color: #111111; color: {TEXT};}}

        QLabel#headerTitle {{ font-weight: 700; font-size: 20px; color: {TEXT}; letter-spacing: 0.5px;}}

        QScrollArea#scroll {{ background: transparent; border: none;}}
        QScrollArea#scroll > QWidget > QWidget {{ background: transparent;}}

        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 0;}}
        QScrollBar::handle:vertical {{ background: #222222; min-height: 30px; border-radius: 5px;}}
        QScrollBar::handle:vertical:hover {{ background: #333333;}}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{ height: 0px;}}

        /* Import Button (Ghost) */
        QPushButton#ghostBtn {{ background-color: transparent; color: {TEXT_DIM}; border: 1px solid {BORDER}; padding: 6px 14px; border-radius: 999px; font-weight: 600; font-size: 11px; min-height: 20px;}}
        QPushButton#ghostBtn:hover {{ background-color: #111111; color: {TEXT}; border: 1px solid {ACCENT};}}

        /* Mod Buttons (Enable/Disable/Open) */
        QPushButton#modBtn {{ background-color: transparent; border-radius: 4px; font-weight: 700; font-size: 11px; padding: 7px 16px; min-height: 20px;}}
        QPushButton#modBtn[state="enable"] {{ color: {ENABLE_CLR}; border: 1px solid {ENABLE_CLR}; background-color: rgba(60, 203, 127, 0.05);}}
        QPushButton#modBtn[state="enable"]:hover {{ background-color: rgba(60, 203, 127, 0.15);}}
        QPushButton#modBtn[state="disable"] {{ color: {DISABLE_CLR}; border: 1px solid {DISABLE_CLR}; background-color: rgba(255, 107, 107, 0.05);}}
        QPushButton#modBtn[state="disable"]:hover {{ background-color: rgba(255, 107, 107, 0.15);}}
        QPushButton#modBtn:disabled {{ color: #444; border: 1px dashed #333; background: transparent;}}

        /* Launch Game Button */
        QPushButton#launchBtn {{ background-color: #eeeeee; color: #050505; border: 1px solid #ffffff; padding: 10px 14px; border-radius: 4px; font-weight: 800; font-size: 13px;}}
        QPushButton#launchBtn:hover {{ background-color: #ffffff;}}
        QPushButton#launchBtn:pressed {{ background-color: #cccccc;}}
        """

def main():
    _ensure_dirs()
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    app._main_window = win
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
