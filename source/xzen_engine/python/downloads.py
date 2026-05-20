import os
import sys
import json
import subprocess
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets


def project_root() -> Path:
    # this file: source/xzen_engine/python/downloads.py
    # parents: python -> xzen_engine -> source -> project root
    return Path(__file__).resolve().parents[3]


ROOT = project_root()
COMMUNITY_PLUGINS_DIR = ROOT / "source" / "community_plugins"

ICON_SIZE = 84

# ===== Stealth Theme Colors =====
ACCENT   = "#ffffff"
BG_DARK  = "#050505"
PANEL    = "#0a0a0a"
TEXT     = "#eeeeee"
TEXT_DIM = "#888888"
BORDER   = "#333333"

QtNoFocus = getattr(QtCore.Qt, "NoFocus", getattr(QtCore.Qt.FocusPolicy, "NoFocus"))
QtPointingHandCursor = getattr(QtCore.Qt, "PointingHandCursor", getattr(QtCore.Qt.CursorShape, "PointingHandCursor"))


# ---------- JSON helpers ----------
def read_plugin_meta(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def pick_str(meta: dict, *keys: str, default: str = "") -> str:
    for k in keys:
        v = meta.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return default


def pick_author(meta: dict) -> str:
    return pick_str(meta, "author", "Author", "creator", "Creator", default="Unknown")


def pick_version(meta: dict) -> str:
    return pick_str(meta, "version", "Version", "app_version", "appVersion", default="Unknown")


def pick_name(meta: dict, fallback: str) -> str:
    return pick_str(meta, "name", "Name", default=fallback)


def pick_description(meta: dict) -> str:
    return pick_str(meta, "description", "desc", "Description", default="Community tool launcher.")


def pick_icon_filename(meta: dict) -> str:
    return pick_str(meta, "icon", "Icon", default="")


def pick_entry(meta: dict) -> str:
    return pick_str(meta, "entry", "Entry", "run", "Run", default="")


def resolve_icon_path(plugin_dir: Path, meta: dict) -> Path | None:
    filename = pick_icon_filename(meta)

    # fallback icon.png
    if not filename:
        fallback = plugin_dir / "icon.png"
        return fallback if fallback.exists() else None

    p = (plugin_dir / filename).resolve()

    try:
        p.relative_to(plugin_dir.resolve())
    except Exception:
        return None

    if p.suffix.lower() != ".png":
        return None

    return p if p.exists() else None


def load_icon_pixmap(path: Path, size: int) -> QtGui.QPixmap | None:
    pm = QtGui.QPixmap(str(path))
    if pm.isNull():
        return None
    return pm.scaled(size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)


# ---------- runnable helpers ----------
def kind_from_suffix(p: Path) -> str:
    s = p.suffix.lower()
    if s == ".exe":
        return "exe"
    if s == ".bat":
        return "bat"
    if s == ".py":
        return "py"
    return "none"


def resolve_entry_runnable(plugin_dir: Path, meta: dict) -> tuple[Path | None, str]:
    entry = pick_entry(meta)
    if not entry:
        return None, "none"

    p = (plugin_dir / entry).resolve()

    try:
        p.relative_to(plugin_dir.resolve())
    except Exception:
        return None, "none"

    if not p.exists() or not p.is_file():
        return None, "none"

    k = kind_from_suffix(p)
    if k == "none":
        return None, "none"

    return p, k


def auto_pick_runnable(plugin_dir: Path) -> tuple[Path | None, str]:
    if not plugin_dir.exists():
        return None, "none"

    files = [p for p in plugin_dir.iterdir() if p.is_file()]

    exes = sorted([p for p in files if p.suffix.lower() == ".exe"], key=lambda x: x.name.lower())
    bats = sorted([p for p in files if p.suffix.lower() == ".bat"], key=lambda x: x.name.lower())
    pys  = sorted([p for p in files if p.suffix.lower() == ".py"],  key=lambda x: x.name.lower())

    if exes:
        return exes[0], "exe"
    if bats:
        return bats[0], "bat"
    if pys:
        return pys[0], "py"

    return None, "none"


def run_runnable(path: Path, kind: str):
    """Return subprocess.Popen handle or None."""
    try:
        if sys.platform != "win32":
            return None
        if not path.exists():
            return None

        cwd = str(path.parent)

        if kind == "exe":
            return subprocess.Popen([str(path)], cwd=cwd)

        if kind == "bat":
            cmd_exe = os.environ.get("ComSpec", "cmd.exe")
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            return subprocess.Popen([cmd_exe, "/c", str(path)], cwd=cwd, creationflags=creationflags)

        if kind == "py":
            py_cmd = sys.executable if not getattr(sys, "frozen", False) else "python"
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            return subprocess.Popen([py_cmd, str(path)], cwd=cwd, creationflags=creationflags)

        return None
    except Exception:
        return None


def discover_plugins() -> list[dict]:
    plugins: list[dict] = []
    if not COMMUNITY_PLUGINS_DIR.exists():
        return plugins

    folders = sorted([p for p in COMMUNITY_PLUGINS_DIR.iterdir() if p.is_dir()], key=lambda x: x.name.lower())

    for d in folders:
        meta = read_plugin_meta(d / "plugin.json")

        name = pick_name(meta, d.name)
        author = pick_author(meta)
        version = pick_version(meta)
        desc = pick_description(meta)
        icon_path = resolve_icon_path(d, meta)

        run_path, run_kind = resolve_entry_runnable(d, meta)
        if not run_path:
            run_path, run_kind = auto_pick_runnable(d)

        plugins.append({
            "dir": d,
            "name": name,
            "author": author,
            "version": version,
            "description": desc,
            "icon_path": icon_path,
            "run_path": run_path,
            "run_kind": run_kind,
        })

    return plugins


# ---------- styles we FORCE on buttons ----------
def white_btn_qss() -> str:
    return f"""
    QPushButton {{
        background-color: {TEXT};
        color: {BG_DARK};
        border: 1px solid {ACCENT};
        padding: 8px 12px;
        border-radius: 7px;
        font-weight: 900;
        font-size: 12px;
        min-height: 32px;
    }}
    QPushButton:hover {{
        background-color: #ffffff;
    }}
    QPushButton:pressed {{
        background-color: #cccccc;
    }}
    QPushButton:disabled {{
        background-color: #171717;
        color: #555555;
        border: 1px solid #2a2a2a;
    }}
    """


def ghost_btn_qss_small() -> str:
    return f"""
    QPushButton {{
        background: transparent;
        color: {TEXT_DIM};
        border: 1px solid {BORDER};
        padding: 6px 10px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 10px;
        min-height: 26px;
    }}
    QPushButton:hover {{
        background: #111111;
        color: {TEXT};
        border-color: {ACCENT};
    }}
    """


# ---------- Plugin Card ----------
class PluginCard(QtWidgets.QFrame):
    def __init__(self, plugin: dict, parent=None):
        super().__init__(parent)
        self.plugin = plugin

        self._proc = None
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._poll_process)

        self.setObjectName("pluginCard")
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.setMinimumHeight(110)

        self._build_ui()
        self._apply_meta()

    def _build_ui(self):
        c = QtWidgets.QHBoxLayout(self)
        c.setContentsMargins(16, 14, 16, 14)
        c.setSpacing(14)

        self.icon = QtWidgets.QLabel()
        self.icon.setObjectName("pluginIcon")
        self.icon.setFixedSize(ICON_SIZE, ICON_SIZE)
        self.icon.setAlignment(QtCore.Qt.AlignCenter)

        info = QtWidgets.QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(6)

        self.name = QtWidgets.QLabel(self.plugin.get("name", "Plugin"))
        self.name.setObjectName("pluginName")

        pills_row = QtWidgets.QHBoxLayout()
        pills_row.setContentsMargins(0, 0, 0, 0)
        pills_row.setSpacing(8)

        self.pill_author = QtWidgets.QLabel("Author: Unknown")
        self.pill_author.setObjectName("pill")

        self.pill_version = QtWidgets.QLabel("Version: Unknown")
        self.pill_version.setObjectName("pill")

        pills_row.addWidget(self.pill_author, 0)
        pills_row.addWidget(self.pill_version, 0)
        pills_row.addStretch(1)

        self.desc = QtWidgets.QLabel("")
        self.desc.setObjectName("pluginDesc")
        self.desc.setWordWrap(True)

        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("pluginStatus")

        info.addWidget(self.name)
        info.addLayout(pills_row)
        info.addWidget(self.desc)
        info.addWidget(self.status)

        # RIGHT SIDE FIXED WIDTH so button cannot vanish
        actions_wrap = QtWidgets.QWidget()
        actions_wrap.setFixedWidth(140)

        actions = QtWidgets.QVBoxLayout(actions_wrap)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self.btn_run = QtWidgets.QPushButton("Run")
        self.btn_run.setCursor(QtGui.QCursor(QtPointingHandCursor))
        self.btn_run.setFocusPolicy(QtNoFocus)
        self.btn_run.setFixedWidth(120)

        # FORCE WHITE BUTTON HERE
        self.btn_run.setStyleSheet(white_btn_qss())

        self.btn_run.clicked.connect(self.on_run_clicked)

        actions.addStretch(1)
        actions.addWidget(self.btn_run, 0, alignment=QtCore.Qt.AlignRight)
        actions.addStretch(1)

        c.addWidget(self.icon, 0)
        c.addLayout(info, 1)
        c.addWidget(actions_wrap, 0)

    def _apply_meta(self):
        self.pill_author.setText(f"Author: {self.plugin.get('author', 'Unknown')}")
        self.pill_version.setText(f"Version: {self.plugin.get('version', 'Unknown')}")
        self.desc.setText(self.plugin.get("description", "Community tool launcher."))

        icon_path = self.plugin.get("icon_path")
        if isinstance(icon_path, Path) and icon_path.exists():
            pm = load_icon_pixmap(icon_path, ICON_SIZE)
            if pm:
                self.icon.setPixmap(pm)

        run_path = self.plugin.get("run_path")
        run_kind = self.plugin.get("run_kind", "none")

        if not run_path or run_kind == "none":
            self.btn_run.setEnabled(False)
            self.btn_run.setToolTip("No runnable found. Put .exe/.bat/.py in folder or set entry in plugin.json.")
        else:
            self.btn_run.setEnabled(True)
            self.btn_run.setToolTip(str(run_path))

    def on_run_clicked(self):
        run_path: Path | None = self.plugin.get("run_path")
        run_kind: str = self.plugin.get("run_kind", "none")

        if not run_path or run_kind == "none":
            self.status.setText("No runnable found")
            return

        self.status.setText("Running...")

        proc = run_runnable(run_path, run_kind)
        if not proc:
            self.status.setText("")
            QtWidgets.QMessageBox.critical(self, "Failed", f"Could not run:\n{run_path}")
            return

        self._proc = proc
        self._poll_timer.start()

    def _poll_process(self):
        if not self._proc:
            self._poll_timer.stop()
            self.status.setText("")
            return

        if self._proc.poll() is not None:
            self._poll_timer.stop()
            self._proc = None
            self.status.setText("")


# ---------- Page ----------
class DownloadsPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DownloadsRoot")
        self.setStyleSheet(self._qss())
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header
        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)

        title = QtWidgets.QLabel("Community Plugins")
        title.setObjectName("pageTitle")

        top.addWidget(title, 0)
        top.addStretch(1)
        root.addLayout(top)

        # Panel
        panel = QtWidgets.QFrame()
        panel.setObjectName("panel")
        p = QtWidgets.QVBoxLayout(panel)
        p.setContentsMargins(14, 14, 14, 14)
        p.setSpacing(10)

        # Scroll list
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("scroll")
        self.scroll.setStyleSheet("border: none; background: transparent;")

        self.wrap = QtWidgets.QWidget()
        self.v = QtWidgets.QVBoxLayout(self.wrap)
        self.v.setContentsMargins(0, 0, 0, 0)
        self.v.setSpacing(12)

        self.scroll.setWidget(self.wrap)
        p.addWidget(self.scroll, 1)

        # Bottom bar with refresh (bottom-right)
        bottom = QtWidgets.QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)

        bottom.addStretch(1)

        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_refresh.setCursor(QtGui.QCursor(QtPointingHandCursor))
        self.btn_refresh.setFocusPolicy(QtNoFocus)
        self.btn_refresh.setFixedWidth(86)  # smaller
        self.btn_refresh.setStyleSheet(ghost_btn_qss_small())
        self.btn_refresh.clicked.connect(self.refresh)

        bottom.addWidget(self.btn_refresh, 0, alignment=QtCore.Qt.AlignRight)
        p.addLayout(bottom)

        root.addWidget(panel, 1)

    def _clear(self):
        while self.v.count():
            it = self.v.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)

    def refresh(self):
        self._clear()

        if not COMMUNITY_PLUGINS_DIR.exists():
            lbl = QtWidgets.QLabel(f"Missing folder:\n{COMMUNITY_PLUGINS_DIR}")
            lbl.setObjectName("emptyText")
            lbl.setWordWrap(True)
            self.v.addWidget(lbl)
            self.v.addStretch(1)
            return

        plugins = discover_plugins()
        if not plugins:
            lbl = QtWidgets.QLabel("No plugin folders found in source/community_plugins")
            lbl.setObjectName("emptyText")
            lbl.setWordWrap(True)
            self.v.addWidget(lbl)
            self.v.addStretch(1)
            return

        for pl in plugins:
            self.v.addWidget(PluginCard(pl))

        self.v.addStretch(1)

    def _qss(self) -> str:
        return f"""
        * {{
            outline: none;
        }}

        QWidget#DownloadsRoot {{
            background: {BG_DARK};
            color: {TEXT};
            font-family: "Segoe UI", system-ui, sans-serif;
            font-size: 13px;
        }}

        QLabel#pageTitle {{
            font-weight: 700;
            font-size: 20px;
            color: {TEXT};
            letter-spacing: 0.5px;
        }}

        QFrame#panel {{
            background: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 8px;
        }}

        QLabel#emptyText {{
            color: {TEXT_DIM};
            padding: 16px;
            background: #070707;
            border: 1px solid {BORDER};
            border-radius: 10px;
        }}

        QFrame#pluginCard {{
            background: #070707;
            border: 1px solid {BORDER};
            border-radius: 10px;
        }}

        QLabel#pluginIcon {{
            background: transparent;
            border: none;
        }}

        QLabel#pluginName {{
            color: {TEXT};
            font-weight: 900;
            font-size: 14px;
        }}

        QLabel#pluginDesc {{
            color: {TEXT_DIM};
            font-size: 12px;
            line-height: 1.35;
        }}

        QLabel#pluginStatus {{
            color: {TEXT_DIM};
            font-size: 11px;
            padding-top: 2px;
        }}

        QLabel#pill {{
            background: #0b0b0b;
            border: 1px solid {BORDER};
            color: {TEXT_DIM};
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 700;
        }}
        """
