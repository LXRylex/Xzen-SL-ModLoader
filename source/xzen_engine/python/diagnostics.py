from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional
import html
import json
import os
import py_compile
import re
import sys

from PyQt5 import QtCore, QtGui, QtWidgets


BG_DARK = "#050505"
PANEL = "#0a0a0a"
SURFACE = "#101010"
TEXT = "#eeeeee"
TEXT_DIM = "#888888"
BORDER = "#333333"
GOOD = "#3CCB7F"
WARN = "#F1C26E"
BAD = "#FF6B6B"

APPID = 1352080
GAME_HINTS = ("smash", "legend")

QtLeftButton = getattr(QtCore.Qt, "LeftButton", getattr(QtCore.Qt.MouseButton, "LeftButton"))
QtNoFocus = getattr(QtCore.Qt, "NoFocus", getattr(QtCore.Qt.FocusPolicy, "NoFocus"))
QtPointingHandCursor = getattr(QtCore.Qt, "PointingHandCursor", getattr(QtCore.Qt.CursorShape, "PointingHandCursor"))


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


ROOT = project_root()
SOURCE_DIR = ROOT / "source"
PYTHON_DIR = SOURCE_DIR / "xzen_engine" / "python"
USER_DATA_DIR = SOURCE_DIR / "profile" / "user_data"
PATHS_JSON = USER_DATA_DIR / "paths.json"
APP_SETTINGS_JSON = USER_DATA_DIR / "app_settings.json"
MODDED_DIR = SOURCE_DIR / "mods" / "modded"
BATS_DIR = SOURCE_DIR / "xzen_engine" / "bats"
SETTINGS_DIR = SOURCE_DIR / "xzen_engine" / "settings"


class Check:
    def __init__(self, level: str, label: str, detail: str = ""):
        self.level = level
        self.label = label
        self.detail = detail


def clean_text(value) -> str:
    return str(value or "").strip()


def describe_path(path: Path) -> str:
    try:
        if path.exists():
            kind = "dir" if path.is_dir() else "file"
            return f"{path} ({kind})"
    except Exception as e:
        return f"{path} (access error: {e})"
    return f"{path} (missing)"


def load_json_file(path: Path) -> tuple[Optional[dict], str]:
    if not path.exists():
        return None, "missing"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return None, f"invalid JSON: {e}"
    if not isinstance(raw, dict):
        return None, "JSON root is not an object"
    return raw, "ok"


def count_files(path: Path) -> int:
    try:
        return sum(1 for item in path.rglob("*") if item.is_file())
    except Exception:
        return 0


def first_existing(paths: Iterable[Path]) -> Optional[Path]:
    for path in paths:
        try:
            if path.exists():
                return path
        except Exception:
            pass
    return None


def steam_root() -> Optional[Path]:
    try:
        import winreg  # type: ignore
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = winreg.QueryValueEx(key, "SteamPath")
            path = Path(value)
            if path.exists():
                return path
    except Exception:
        pass

    return first_existing(
        [
            Path("C:/Program Files (x86)/Steam"),
            Path("C:/Program Files/Steam"),
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Steam",
            Path(os.environ.get("PROGRAMFILES", "")) / "Steam",
        ]
    )


def steam_libraries(root: Path) -> list[Path]:
    libs = [root]
    vdf = root / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        try:
            text = vdf.read_text(encoding="utf-8", errors="ignore")
            for raw in re.findall(r'"path"\s*"([^"]+)"', text, flags=re.IGNORECASE):
                path = Path(raw.replace("\\\\", "\\"))
                if path.exists():
                    libs.append(path)
        except Exception:
            pass

    unique: list[Path] = []
    seen: set[str] = set()
    for path in libs:
        try:
            key = str(path.resolve()).lower()
        except Exception:
            key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def find_steam_game() -> tuple[Optional[Path], Optional[Path], Optional[Path]]:
    root = steam_root()
    if root is None:
        return None, None, None

    manifest: Optional[Path] = None
    game_dir: Optional[Path] = None
    for lib in steam_libraries(root):
        candidate = lib / "steamapps" / f"appmanifest_{APPID}.acf"
        if not candidate.exists():
            continue
        manifest = candidate
        try:
            text = candidate.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r'"installdir"\s*"([^"]+)"', text, flags=re.IGNORECASE)
            if match:
                path = lib / "steamapps" / "common" / match.group(1)
                if path.exists():
                    game_dir = path
        except Exception:
            pass
        break

    return root, manifest, game_dir


def python_syntax_status(path: Path) -> Check:
    if not path.exists():
        return Check("FAIL", f"Python module missing: {path.name}", str(path))
    try:
        py_compile.compile(str(path), doraise=True)
    except Exception as e:
        return Check("FAIL", f"Python syntax failed: {path.name}", str(e))
    return Check("OK", f"Python syntax ok: {path.name}", str(path))


def collect_checks() -> list[Check]:
    checks: list[Check] = []

    checks.append(Check("INFO", "Runtime", f"frozen={getattr(sys, 'frozen', False)} | executable={sys.executable}"))
    checks.append(Check("INFO", "Project root", str(ROOT)))

    required_dirs = [
        SOURCE_DIR,
        PYTHON_DIR,
        USER_DATA_DIR,
        MODDED_DIR,
        BATS_DIR,
        SETTINGS_DIR,
    ]
    for path in required_dirs:
        checks.append(Check("OK" if path.exists() else "FAIL", f"Required folder: {path.name}", describe_path(path)))

    required_files = [
        PYTHON_DIR / "settings.py",
        PYTHON_DIR / "feedback.py",
        PYTHON_DIR / "diagnostics.py",
        PYTHON_DIR / "library.py",
        PYTHON_DIR / "online_service.py",
        PYTHON_DIR / "xzen_service.py",
        SETTINGS_DIR / "steam_verification.bat",
        BATS_DIR / "launch_game.bat",
        BATS_DIR / "open_UI_Mods.bat",
        APP_SETTINGS_JSON,
        PATHS_JSON,
    ]
    if getattr(sys, "frozen", False):
        required_files.append(Path(sys.executable))
    else:
        required_files.append(ROOT / "prototype.py")

    for path in required_files:
        checks.append(Check("OK" if path.exists() else "FAIL", f"Required file: {path.name}", describe_path(path)))

    for folder_name in ("characters", "emoticon", "custom_stages", "ui_mods"):
        folder = MODDED_DIR / folder_name
        if not folder.exists():
            checks.append(Check("FAIL", f"Mod folder missing: {folder_name}", str(folder)))
            continue
        files = count_files(folder)
        level = "OK" if files else "WARN"
        checks.append(Check(level, f"Mod folder: {folder_name}", f"{folder} | files={files}"))

    paths_data, paths_status = load_json_file(PATHS_JSON)
    if paths_data is None:
        checks.append(Check("FAIL", "paths.json", f"{PATHS_JSON} | {paths_status}"))
    else:
        checks.append(Check("OK", "paths.json readable", str(PATHS_JSON)))
        assetbundles = Path(clean_text(paths_data.get("assetbundles_dir")))
        game_exe = Path(clean_text(paths_data.get("game_exe")))
        checks.append(Check("OK" if assetbundles.is_dir() else "FAIL", "AssetBundles path", describe_path(assetbundles)))
        checks.append(Check("OK" if game_exe.is_file() else "FAIL", "Game executable path", describe_path(game_exe)))
        if game_exe.exists() and not any(hint in game_exe.name.lower() for hint in GAME_HINTS):
            checks.append(Check("WARN", "Game exe name looks unusual", game_exe.name))
        expected_data = game_exe.parent / "Smash_Legends_Data" / "StreamingAssets" / "AssetBundles"
        if game_exe.exists() and assetbundles.exists() and expected_data.exists() and assetbundles.resolve() != expected_data.resolve():
            checks.append(Check("WARN", "Saved AssetBundles differs from game exe sibling path", f"saved={assetbundles} | expected={expected_data}"))

    app_settings, settings_status = load_json_file(APP_SETTINGS_JSON)
    if app_settings is None:
        checks.append(Check("FAIL", "app_settings.json", f"{APP_SETTINGS_JSON} | {settings_status}"))
    else:
        checks.append(Check("OK", "app_settings.json readable", str(APP_SETTINGS_JSON)))
        checks.append(Check("INFO", "show_splash_intro", str(bool(app_settings.get("show_splash_intro", False)))))

    root, manifest, game_dir = find_steam_game()
    checks.append(Check("OK" if root else "WARN", "Steam root", str(root or "not found")))
    checks.append(Check("OK" if manifest else "WARN", "Smash Legends Steam manifest", str(manifest or "not found")))
    checks.append(Check("OK" if game_dir else "WARN", "Steam game folder", str(game_dir or "not found")))

    for module_name in ("settings.py", "feedback.py", "diagnostics.py", "library.py", "online_service.py", "xzen_service.py"):
        checks.append(python_syntax_status(PYTHON_DIR / module_name))

    dist_root = ROOT / "dist" / "XZEN-MM"
    if dist_root.exists():
        dist_source = dist_root / "source"
        checks.append(Check("OK", "Local dist build found", str(dist_root)))
        for rel in (
            Path("XZEN-MM.exe"),
            Path("source") / "xzen_engine" / "python" / "settings.py",
            Path("source") / "xzen_engine" / "python" / "diagnostics.py",
            Path("source") / "profile" / "user_data" / "app_settings.json",
            Path("source") / "mods" / "modded",
        ):
            path = dist_root / rel
            checks.append(Check("OK" if path.exists() else "WARN", f"Dist copy: {rel}", describe_path(path)))
        if dist_source.exists():
            checks.append(Check("INFO", "Dist source folder", str(dist_source)))

    return checks


def count_levels(checks: list[Check]) -> dict[str, int]:
    counts = {"OK": 0, "WARN": 0, "FAIL": 0, "INFO": 0}
    for check in checks:
        counts[check.level] = counts.get(check.level, 0) + 1
    return counts


def summary_text(counts: dict[str, int]) -> str:
    return f"Summary: OK={counts['OK']} WARN={counts['WARN']} FAIL={counts['FAIL']} INFO={counts['INFO']}"


def build_report_from_checks(checks: list[Check]) -> str:
    counts = count_levels(checks)
    lines = [
        "XZEN Mod Manager Diagnostics",
        f"Root: {ROOT}",
        summary_text(counts),
        "",
    ]
    for check in checks:
        lines.append(f"[{check.level}] {check.label}")
        if check.detail:
            lines.append(f"    {check.detail}")
    return "\n".join(lines)


def build_report() -> str:
    return build_report_from_checks(collect_checks())


def status_color(level: str) -> str:
    return {
        "OK": GOOD,
        "WARN": WARN,
        "FAIL": BAD,
        "INFO": TEXT_DIM,
    }.get(level, TEXT)


def colored_summary_html(counts: dict[str, int]) -> str:
    return (
        "Summary: "
        f"<span style='color:{GOOD};'>OK={counts['OK']}</span> "
        f"<span style='color:{WARN};'>WARN={counts['WARN']}</span> "
        f"<span style='color:{BAD};'>FAIL={counts['FAIL']}</span> "
        f"<span style='color:{TEXT_DIM};'>INFO={counts['INFO']}</span>"
    )


def build_report_html_from_checks(checks: list[Check]) -> str:
    counts = count_levels(checks)
    lines = [
        f"<div style='color:{TEXT}; font-weight:700;'>XZEN Mod Manager Diagnostics</div>",
        f"<div style='color:{TEXT_DIM};'>Root: {html.escape(str(ROOT))}</div>",
        f"<div>{colored_summary_html(counts)}</div>",
        "<br>",
    ]
    for check in checks:
        color = status_color(check.level)
        label = html.escape(check.label)
        detail = html.escape(check.detail)
        lines.append(
            f"<div><span style='color:{color}; font-weight:700;'>[{check.level}]</span> "
            f"<span style='color:{TEXT};'>{label}</span></div>"
        )
        if detail:
            lines.append(f"<div style='color:{TEXT_DIM}; padding-left:24px;'>{detail}</div>")

    body = "\n".join(lines)
    return (
        f"<div style='font-family:Consolas, monospace; font-size:12px; "
        f"white-space:pre; background:{PANEL}; color:{TEXT};'>{body}</div>"
    )


class CustomTitleBar(QtWidgets.QWidget):
    def __init__(self, parent, title="Diagnostics"):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(35)
        self.start_pos = None

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(10)

        label = QtWidgets.QLabel(title)
        label.setStyleSheet(f"color: {TEXT_DIM}; font-weight: 600; font-size: 12px;")
        close_btn = QtWidgets.QPushButton("X")
        close_btn.setFixedSize(45, 35)
        close_btn.setFocusPolicy(QtNoFocus)
        close_btn.clicked.connect(self.parent.close)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TEXT_DIM}; border: none; font-size: 12px; }}
            QPushButton:hover {{ background-color: {BAD}; color: #000; }}
        """)

        layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event):
        if event.button() == QtLeftButton:
            self.start_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.start_pos:
            delta = event.globalPos() - self.start_pos
            self.parent.move(self.parent.pos() + delta)
            self.start_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.start_pos = None


class DiagnosticsUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFixedSize(760, 620)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        frame = QtWidgets.QFrame()
        frame.setObjectName("root")
        frame_layout = QtWidgets.QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        frame_layout.addWidget(CustomTitleBar(self))

        body = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(18, 16, 18, 16)
        body_layout.setSpacing(10)

        self.summary = QtWidgets.QLabel()
        self.summary.setObjectName("summary")
        self.summary.setTextFormat(QtCore.Qt.RichText)

        self.report = QtWidgets.QTextEdit()
        self.report.setReadOnly(True)
        self.report.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        self._plain_report = ""

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_refresh = QtWidgets.QPushButton("Refresh Scan")
        self.btn_refresh.setObjectName("ActionBtn")
        self.btn_refresh.setFocusPolicy(QtNoFocus)
        self.btn_refresh.setCursor(QtPointingHandCursor)
        self.btn_refresh.clicked.connect(self.refresh)

        self.btn_copy = QtWidgets.QPushButton("Copy Report")
        self.btn_copy.setObjectName("GhostBtn")
        self.btn_copy.setFocusPolicy(QtNoFocus)
        self.btn_copy.setCursor(QtPointingHandCursor)
        self.btn_copy.clicked.connect(self.copy_report)

        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_copy)
        btn_row.addStretch(1)

        body_layout.addWidget(self.summary)
        body_layout.addWidget(self.report, 1)
        body_layout.addLayout(btn_row)
        frame_layout.addWidget(body)

        root.addWidget(frame)
        self.setStyleSheet(self._qss())

    def refresh(self):
        checks = collect_checks()
        counts = count_levels(checks)
        self._plain_report = build_report_from_checks(checks)
        self.report.setHtml(build_report_html_from_checks(checks))
        self.summary.setText(colored_summary_html(counts))

    def copy_report(self):
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.clipboard().setText(self._plain_report)
            self.summary.setText(self.summary.text() + " | copied")

    def _qss(self) -> str:
        return f"""
        QFrame#root {{
            background: {BG_DARK};
            border: 1px solid {BORDER};
            border-radius: 6px;
        }}
        QWidget {{
            background: {BG_DARK};
            color: {TEXT};
            font-family: "Segoe UI", sans-serif;
            font-size: 13px;
        }}
        QLabel#summary {{
            color: {TEXT};
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 4px;
            padding: 8px 10px;
            font-weight: 700;
        }}
        QTextEdit {{
            background: {PANEL};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 4px;
            padding: 10px;
            font-family: "Consolas", monospace;
            font-size: 12px;
        }}
        QPushButton#ActionBtn {{
            background-color: #eeeeee;
            color: #050505;
            border: none;
            padding: 9px 14px;
            border-radius: 4px;
            font-weight: 700;
        }}
        QPushButton#ActionBtn:hover {{
            background-color: #ffffff;
        }}
        QPushButton#GhostBtn {{
            background: transparent;
            color: {TEXT};
            border: 1px solid {BORDER};
            padding: 9px 14px;
            border-radius: 4px;
            font-weight: 600;
        }}
        QPushButton#GhostBtn:hover {{
            background-color: #111111;
            border: 1px solid {TEXT};
        }}
        QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: #333; min-height: 20px; border-radius: 4px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0; }}
        QScrollBar::handle:horizontal {{ background: #333; min-width: 20px; border-radius: 4px; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
        """


def main():
    app = QtWidgets.QApplication(sys.argv or ["diagnostics"])
    ui = DiagnosticsUI()
    ui.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
