from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Tuple, Any
import importlib.util
import json, os, sys, mimetypes

from PyQt5 import QtCore, QtGui, QtWidgets

WEBHOOK_URL = "https://discord.com/api/webhooks/1275721755863810119/MSgMj3Ex9SiwuHihI8kb_tEonaMRvqpjYc0wuF0vQmmjvj98g97MHmacP7cJf7ZsFSzw"
APP_VERSION = "4.0.6"
MAX_DESC = 2000
MAX_FILE_BYTES = 8_000_000
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# ===== Xzen Stealth Theme =====
ACCENT   = "#ffffff"   
BG_DARK  = "#050505"   
PANEL    = "#0a0a0a"   
TEXT     = "#eeeeee"   
TEXT_DIM = "#888888"   
BORDER   = "#333333"
ENABLE_CLR  = "#3CCB7F" 
DISABLE_CLR = "#FF6B6B" 

# Qt Compat
QtAlignCenter   = getattr(QtCore.Qt, "AlignCenter",   getattr(QtCore.Qt.AlignmentFlag, "AlignCenter"))
QtLeftButton    = getattr(QtCore.Qt, "LeftButton",    getattr(QtCore.Qt.MouseButton, "LeftButton"))
QtPointingHandCursor = getattr(QtCore.Qt, "PointingHandCursor", getattr(QtCore.Qt.CursorShape, "PointingHandCursor"))
QtNoFocus       = getattr(QtCore.Qt, "NoFocus",       getattr(QtCore.Qt.FocusPolicy, "NoFocus"))
QtKeepAspectExpand = getattr(QtCore.Qt, "KeepAspectRatioByExpanding", getattr(QtCore.Qt.AspectRatioMode, "KeepAspectRatioByExpanding"))
QtSmoothTransform  = getattr(QtCore.Qt, "SmoothTransformation", getattr(QtCore.Qt.TransformationMode, "SmoothTransformation"))

# ---------------- utils ----------------
def _project_root() -> Path:
    # Adjust as needed for your folder structure
    return Path(__file__).resolve().parents[3] 

def _user_data_dir() -> Path:
    return _project_root() / "source" / "profile" / "user_data"

def _log_path() -> Path:
    return _user_data_dir() / "user.logs"

def _diagnostics_report_path() -> Path:
    return _user_data_dir() / "latest_diagnostics_report.txt"

def _latest_log_paths(limit: int = 3) -> List[Path]:
    user_data = _user_data_dir()
    if not user_data.exists():
        return []

    logs = []
    for path in user_data.iterdir():
        if not path.is_file():
            continue
        name = path.name.lower()
        if name.endswith((".log", ".logs")) or "log" in name:
            logs.append(path)

    preferred = _log_path()
    ordered = sorted(logs, key=lambda p: (p != preferred, -p.stat().st_mtime if p.exists() else 0))
    return ordered[:limit]

def _build_diagnostics_report_file() -> Optional[Path]:
    module_path = Path(__file__).resolve().with_name("diagnostics.py")
    if not module_path.exists():
        return None

    try:
        spec = importlib.util.spec_from_file_location("xzen_feedback_diagnostics", str(module_path))
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        build_report = getattr(module, "build_report", None)
        if not callable(build_report):
            return None

        report_path = _diagnostics_report_path()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(str(build_report()), encoding="utf-8")
        return report_path
    except Exception as e:
        safe_print(f"[feedback] diagnostics scan failed: {e}")
        return None

def _size_ok(p: Path) -> bool:
    try:
        return p.stat().st_size <= MAX_FILE_BYTES
    except Exception:
        return False

def _mime_for(p: Path) -> str:
    mt, _ = mimetypes.guess_type(str(p))
    return mt or "application/octet-stream"

def safe_print(msg: str) -> None:
    try:
        sys.stdout.buffer.write((msg + "\n").encode("utf-8", "replace"))
        sys.stdout.flush()
    except Exception:
        pass

# -------------- webhook ----------------
def _make_payload(name: str, title: str, desc: str, version: str) -> dict:
    lines = [
        f"**{title or 'No title'}**",
        f"Reporter: {name or 'Anonymous'}",
        f"Version: {version or APP_VERSION}",
        "",
        (desc or "-")[:MAX_DESC],
    ]
    content = "\n".join(lines)
    if len(content) > 2000:
        content = content[:2000]
    return {"username": name or "Anonymous", "content": content}

def _send_to_webhook(name: str, title: str, desc: str, version: str, diagnostics: Optional[Path], logs: List[Path], shots: List[Path]) -> Tuple[int, str]:
    try:
        import requests
    except Exception:
        msg = "Install 'requests': python -m pip install requests"
        safe_print("[feedback] " + msg); return 1, msg

    payload = _make_payload(name, title, desc, version)
    files: dict[str, tuple] = {}
    opened = []
    try:
        idx = 0
        if diagnostics and diagnostics.exists():
            f = open(diagnostics, "rb"); opened.append(f)
            files[f"files[{idx}]"] = ("diagnostics_report.txt", f, "text/plain"); idx += 1
        for logp in logs:
            f = open(logp, "rb"); opened.append(f)
            files[f"files[{idx}]"] = (logp.name, f, _mime_for(logp)); idx += 1
        for sp in shots:
            f = open(sp, "rb"); opened.append(f)
            files[f"files[{idx}]"] = (sp.name, f, _mime_for(sp)); idx += 1

        files["payload_json"] = (None, json.dumps(payload, ensure_ascii=False), "application/json")

        safe_print("[feedback] uploading...")
        with requests.Session() as s:
            r = s.post(WEBHOOK_URL, files=files, timeout=30)
        if r.status_code not in (200, 204):
            msg = f"webhook error: HTTP {r.status_code} - {r.text[:300]}"
            safe_print("[feedback] " + msg); return 2, msg
        safe_print("[feedback] sent OK")
        return 0, "Sent successfully"
    except Exception as e:
        msg = f"exception: {e}"
        safe_print("[feedback] " + msg); return 3, msg
    finally:
        for f in opened:
            try: f.close()
            except: pass

# --------------- GUI -------------------
class SendWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(int, str)
    def __init__(self, name: str, title: str, desc: str, version: str, diagnostics: Optional[Path], logs: List[Path], shots: List[Path]):
        super().__init__(); self.name, self.title, self.desc, self.version, self.diagnostics, self.logs, self.shots = name, title, desc, version, diagnostics, logs, shots
    @QtCore.pyqtSlot()
    def run(self):
        code, msg = _send_to_webhook(self.name, self.title, self.desc, self.version, self.diagnostics, self.logs, self.shots)
        self.finished.emit(code, msg)

class CustomTitleBar(QtWidgets.QWidget):
    def __init__(self, parent, title="Report Issue"):
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

    def mousePressEvent(self, event):
        if event.button() == QtLeftButton: self.startPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.startPos:
            delta = event.globalPos() - self.startPos
            self.parent.move(self.parent.pos() + delta)
            self.startPos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.startPos = None

class FeedbackUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setMinimumWidth(560)
        self.setFixedSize(360, 600)
        
        self._bg_thread: Optional[QtCore.QThread] = None
        self._worker: Optional[SendWorker] = None
        self._uploading: bool = False

        self._init_ui()
        self._prefill()

        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._on_about_to_quit)

    def _init_ui(self):
        # Main Container
        self.main_container = QtWidgets.QFrame(self)
        self.main_container.setObjectName("root")
        
        # Main Layout (Vertical)
        self.main_layout = QtWidgets.QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Title Bar
        self.title_bar = CustomTitleBar(self)
        self.main_layout.addWidget(self.title_bar)

        # Content Area
        self.content_widget = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(12)

        # Fields
        self.name = QtWidgets.QLineEdit()
        self.name.setPlaceholderText("Your Name")
        
        self.title = QtWidgets.QLineEdit()
        self.title.setPlaceholderText("Issue Title")

        self.version = QtWidgets.QLineEdit()
        self.version.setText(APP_VERSION)
        self.version.setReadOnly(True)
        self.version.setFocusPolicy(QtNoFocus)
        
        self.desc = QtWidgets.QTextEdit()
        self.desc.setPlaceholderText("Describe the issue. Logs and diagnostics attach automatically.")
        self.desc.setFixedHeight(100)
        
        self.counter = QtWidgets.QLabel("0 / 2000")
        self.counter.setAlignment(QtCore.Qt.AlignRight)
        self.counter.setStyleSheet(f"color:{TEXT_DIM}; font-size: 11px;")

        # Screenshot Inputs
        self.ss1 = QtWidgets.QLineEdit(); self.ss1.setPlaceholderText("Screenshot 1 (Optional)")
        self.ss2 = QtWidgets.QLineEdit(); self.ss2.setPlaceholderText("Screenshot 2 (Optional)")
        
        b1 = QtWidgets.QPushButton("Browse")
        b1.setCursor(QtPointingHandCursor)
        b1.clicked.connect(lambda: self._pick_image(self.ss1))
        
        b2 = QtWidgets.QPushButton("Browse")
        b2.setCursor(QtPointingHandCursor)
        b2.clicked.connect(lambda: self._pick_image(self.ss2))

        # Log Output
        self.log = QtWidgets.QTextEdit(); self.log.setReadOnly(True); self.log.setFixedHeight(80)
        self.log.setPlaceholderText("Status output...")
        self.log.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; font-family: Consolas, monospace;")

        # Action Buttons
        self.btn_send = QtWidgets.QPushButton("Send Report")
        self.btn_send.setCursor(QtPointingHandCursor)
        self.btn_send.setObjectName("AccentBtn")
        
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_cancel.setCursor(QtPointingHandCursor)
        self.btn_cancel.clicked.connect(self.close)

        # Layout Assembly
        # Form
        form_layout = QtWidgets.QFormLayout()
        form_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        form_layout.setSpacing(10)
        form_layout.addRow("Name:", self.name)
        form_layout.addRow("Title:", self.title)
        form_layout.addRow("Version:", self.version)
        
        # Screenshots Grid
        ss_layout = QtWidgets.QGridLayout()
        ss_layout.setSpacing(8)
        ss_layout.addWidget(self.ss1, 0, 0); ss_layout.addWidget(b1, 0, 1)
        ss_layout.addWidget(self.ss2, 1, 0); ss_layout.addWidget(b2, 1, 1)

        # Bottom Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_send)

        # Add to Content
        self.content_layout.addLayout(form_layout)
        self.content_layout.addWidget(QtWidgets.QLabel("Description:"))
        self.content_layout.addWidget(self.desc)
        self.content_layout.addWidget(self.counter)
        self.content_layout.addSpacing(5)
        self.content_layout.addWidget(QtWidgets.QLabel("Screenshots:"))
        self.content_layout.addLayout(ss_layout)
        self.content_layout.addSpacing(5)
        self.content_layout.addWidget(self.log)
        self.content_layout.addLayout(btn_layout)

        self.main_layout.addWidget(self.content_widget)

        # Apply root layout to widget
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.main_container)

        self.setStyleSheet(self._qss())
        self._wire()

    def _wire(self):
        self.desc.textChanged.connect(self._on_desc_changed)
        self.btn_send.clicked.connect(self._on_send_clicked)

    def _prefill(self):
        who = os.getenv("USERNAME") or os.getenv("USER") or ""
        self.name.setText(who)

    def _qss(self) -> str:
        return f"""
        /* Global Reset */
        * {{ outline: none; }}
        QWidget {{ background: {BG_DARK}; color: {TEXT}; font-family: "Segoe UI", sans-serif; font-size: 13px; }}
        
        /* Main Frame Border */
        QFrame#root {{
            border: 1px solid {BORDER};
            border-radius: 6px;
            background: {BG_DARK};
        }}

        /* Inputs */
        QLineEdit, QTextEdit {{
            background: {PANEL};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 4px;
            padding: 6px;
        }}
        QLineEdit:focus, QTextEdit:focus {{
            border: 1px solid {TEXT_DIM};
        }}

        /* Labels */
        QLabel {{ color: {TEXT}; }}

        /* Buttons */
        QPushButton {{
            background: transparent;
            color: {TEXT_DIM};
            border: 1px solid {BORDER};
            padding: 6px 14px;
            border-radius: 4px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            color: {TEXT};
            border-color: {TEXT_DIM};
            background: #111111;
        }}

        /* Accent Button (Send) */
        QPushButton#AccentBtn {{
            background: {TEXT};
            color: {BG_DARK};
            border: 1px solid {TEXT};
            font-weight: 700;
        }}
        QPushButton#AccentBtn:hover {{
            background: #ffffff;
        }}
        QPushButton:disabled {{
            background: #222;
            color: #555;
            border-color: #333;
        }}

        /* Scrollbars */
        QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: #333; min-height: 20px; border-radius: 4px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """

    # --- Logic (Same as before) ---
    def _thread_running(self) -> bool:
        t = self._bg_thread
        if t is None: return False
        try: return t.isRunning()
        except RuntimeError: return False

    def closeEvent(self, a0: Optional[QtGui.QCloseEvent]) -> None:
        if self._uploading and self._thread_running():
            self._append_log("[feedback] finishing background upload...")
            try:
                assert self._bg_thread is not None
                self._bg_thread.wait(30000)
            except RuntimeError: pass
        if a0 is not None: super().closeEvent(a0)
        else: super().closeEvent(QtGui.QCloseEvent())

    def _on_about_to_quit(self):
        if self._uploading and self._thread_running():
            try:
                assert self._bg_thread is not None
                self._bg_thread.wait(30000)
            except RuntimeError: pass

    def _on_desc_changed(self):
        txt = self.desc.toPlainText()
        if len(txt) > MAX_DESC:
            cur = self.desc.textCursor(); pos = cur.position()
            self.desc.blockSignals(True); self.desc.setPlainText(txt[:MAX_DESC]); self.desc.blockSignals(False)
            cur.setPosition(min(pos, MAX_DESC)); self.desc.setTextCursor(cur)
        self.counter.setText(f"{len(self.desc.toPlainText())} / {MAX_DESC}")

    def _pick_image(self, target_le: QtWidgets.QLineEdit):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select image", str(Path.home()), "Images (*.png *.jpg *.jpeg *.webp *.gif)")
        if fn: target_le.setText(fn)

    def _append_log(self, text: str):
        self.log.append(text); safe_print(text)

    def _validate_image(self, p: str) -> Optional[Path]:
        if not p.strip(): return None
        sp = Path(p)
        if not sp.exists() or not sp.is_file(): self._append_log(f"[warn] not found: {sp}"); return None
        if sp.suffix.lower() not in ALLOWED_IMAGE_EXT: self._append_log(f"[warn] unsupported image type: {sp.suffix}"); return None
        if not _size_ok(sp): self._append_log(f"[warn] too large (> {MAX_FILE_BYTES} bytes): {sp.name}"); return None
        return sp

    def _gather_inputs(self) -> Tuple[str, str, str, str, Optional[Path], List[Path], List[Path]]:
        name  = (self.name.text() or "Anonymous").strip()
        title = (self.title.text() or "No title").strip()
        desc  = self.desc.toPlainText().strip()[:MAX_DESC]
        version = APP_VERSION
        diagnostics = _build_diagnostics_report_file()
        if diagnostics:
            self._append_log(f"[feedback] attached diagnostics: {diagnostics.name}")
        else:
            self._append_log("[warn] diagnostics report could not be generated")

        shots: List[Path] = []
        for le in (self.ss1, self.ss2):
            sp = self._validate_image(le.text())
            if sp: shots.append(sp)

        logs: List[Path] = []
        for log_path in _latest_log_paths():
            if not log_path.exists():
                continue
            if not _size_ok(log_path):
                self._append_log(f"[warn] {log_path.name} too large (> {MAX_FILE_BYTES} bytes); skipping.")
                continue
            logs.append(log_path)
        if logs:
            self._append_log("[feedback] attached logs: " + ", ".join(p.name for p in logs))
        else:
            self._append_log(f"[warn] logs not found: {_user_data_dir()}")

        return name, title, desc, version, diagnostics, logs, shots

    def _set_busy(self, busy: bool):
        for w in (self.name, self.title, self.desc, self.ss1, self.ss2, self.btn_send):
            w.setEnabled(not busy)

    def _on_send_clicked(self):
        name, title, desc, version, diagnostics, logs, shots = self._gather_inputs()
        self._append_log("[feedback] starting upload..."); self._set_busy(True)

        self._bg_thread = QtCore.QThread(self)
        self._worker = SendWorker(name, title, desc, version, diagnostics, logs, shots)
        self._worker.moveToThread(self._bg_thread)
        self._bg_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_send_finished)
        self._worker.finished.connect(self._bg_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._bg_thread.finished.connect(self._on_thread_finished)
        self._bg_thread.finished.connect(self._bg_thread.deleteLater)
        self._uploading = True
        self._bg_thread.start()

    @QtCore.pyqtSlot()
    def _on_thread_finished(self):
        self._bg_thread = None
        self._worker = None

    @QtCore.pyqtSlot(int, str)
    def _on_send_finished(self, code: int, msg: str):
        self._uploading = False
        self._set_busy(False)
        if code == 0:
            self._append_log("[feedback] sent OK")
            QtWidgets.QMessageBox.information(self, "Feedback", "Sent successfully. Thanks!")
            self.close()
        else:
            self._append_log(f"[feedback] failed ({code}): {msg}")
            QtWidgets.QMessageBox.warning(self, "Feedback", f"Failed to send ({code}).\n{msg}")

def main():
    app = QtWidgets.QApplication(sys.argv or ["feedback"])
    ui = FeedbackUI()
    ui.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
