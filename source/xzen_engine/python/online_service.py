import datetime
import http.client
import importlib.util
import json
import mimetypes
import os
import re
import sys
import zipfile
from pathlib import Path
from urllib import parse as urllib_parse

from PyQt5 import QtCore, QtGui, QtWidgets


ACCENT = "#ffffff"
BG_DARK = "#050505"
PANEL = "#0a0a0a"
SURFACE = "#101010"
TEXT = "#eeeeee"
TEXT_DIM = "#888888"
BORDER = "#333333"
GOOD = "#6919AA"

DEFAULT_API_BASE = "http://node.waifly.com:28183"

QtNoFocus = getattr(QtCore.Qt, "NoFocus", getattr(QtCore.Qt.FocusPolicy, "NoFocus"))
QtPointingHandCursor = getattr(QtCore.Qt, "PointingHandCursor", getattr(QtCore.Qt.CursorShape, "PointingHandCursor"))


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[3]


ROOT = project_root()
USER_DATA_DIR = ROOT / "source" / "profile" / "user_data"
ONLINE_SERVICE_LOG = USER_DATA_DIR / "online_service.log"
MODDED_DIR = ROOT / "source" / "mods" / "modded"


def ensure_dirs():
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)


def clean_text(value) -> str:
    return str(value or "").strip()


def safe_archive_name(value: str) -> str:
    name = clean_text(value) or "modded"
    name = re.sub(r'[<>:"/\\\\|?*]+', "-", name).strip(". ")
    return name or "modded"


def packed_mods_zip_path(user_id: str) -> Path:
    return USER_DATA_DIR / f"{safe_archive_name(user_id)} mods.zip"


def create_modded_zip(user_id: str, progress_callback=None) -> tuple[Path, int]:
    ensure_dirs()
    if not MODDED_DIR.exists() or not MODDED_DIR.is_dir():
        raise FileNotFoundError(f"Modded folder was not found: {MODDED_DIR}")

    files = [path for path in MODDED_DIR.rglob("*") if path.is_file()]
    if not files:
        raise ValueError(f"No files were found in {MODDED_DIR}")

    total_bytes = sum(path.stat().st_size for path in files)
    processed_bytes = 0
    if progress_callback is not None:
        progress_callback(0)

    zip_path = packed_mods_zip_path(user_id)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(MODDED_DIR)
            archive.write(path, arcname=Path("modded") / relative)
            processed_bytes += path.stat().st_size
            if progress_callback is not None:
                progress_callback(int((processed_bytes / max(total_bytes, 1)) * 100))

    return zip_path, len(files)


def load_xzen_service_module():
    module = sys.modules.get("xzen_service")
    if module is not None:
        return module

    module_path = Path(__file__).with_name("xzen_service.py")
    spec = importlib.util.spec_from_file_location("xzen_service", str(module_path))
    if not spec or not spec.loader:
        raise ImportError(f"Unable to load xzen_service from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["xzen_service"] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


xzen_service = load_xzen_service_module()


class IcySmoothScrollArea(QtWidgets.QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._base_duration_ms = 460
        self._settle_duration_ms = 380
        self._wheel_step = 40
        self._momentum = 0.0
        self._max_momentum = 260.0
        self._filter_targets: set[int] = set()

        self._scroll_anim = QtCore.QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._scroll_anim.setDuration(self._base_duration_ms)
        self._scroll_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        self._settle_timer = QtCore.QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.timeout.connect(self._apply_settle)

        self.viewport().installEventFilter(self)
        self._remember_filter_target(self.viewport())

    def setWidget(self, widget):
        super().setWidget(widget)
        self._install_scroll_filters(widget)

    def wheelEvent(self, event):
        if self._handle_wheel_event(event):
            return
        super().wheelEvent(event)

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.ChildAdded:
            child = event.child()
            if isinstance(child, QtWidgets.QWidget):
                self._install_scroll_filters(child)
        if event.type() == QtCore.QEvent.Wheel and self._should_handle_wheel_from(watched):
            if self._handle_wheel_event(event):
                return True
        return super().eventFilter(watched, event)

    def _remember_filter_target(self, widget):
        if widget is None:
            return
        self._filter_targets.add(id(widget))

    def _install_scroll_filters(self, root):
        if root is None:
            return

        stack = [root]
        while stack:
            widget = stack.pop()
            if widget is None or id(widget) in self._filter_targets:
                continue
            widget.installEventFilter(self)
            self._remember_filter_target(widget)
            for child in widget.findChildren(QtWidgets.QWidget):
                if id(child) not in self._filter_targets:
                    stack.append(child)

    def _nearest_scroll_area(self, widget):
        current = widget if isinstance(widget, QtWidgets.QWidget) else None
        while current is not None:
            if isinstance(current, IcySmoothScrollArea):
                return current
            current = current.parentWidget()
        return None

    def _should_handle_wheel_from(self, watched):
        if not isinstance(watched, QtWidgets.QWidget):
            return False

        owner = self._nearest_scroll_area(watched)
        if owner is not None and owner is not self:
            return False

        if isinstance(watched, (QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
            bar = watched.verticalScrollBar()
            if bar is not None and bar.maximum() > bar.minimum():
                return False

        return True

    def _wheel_distance(self, event):
        pixel_delta = event.pixelDelta().y()
        if pixel_delta:
            return -pixel_delta * 0.9

        angle_delta = event.angleDelta().y()
        if not angle_delta:
            return 0.0

        return -(angle_delta / 120.0) * self._wheel_step

    def _handle_wheel_event(self, event):
        bar = self.verticalScrollBar()
        if bar.maximum() <= bar.minimum():
            event.ignore()
            return False

        distance = self._wheel_distance(event)
        if not distance:
            event.ignore()
            return False

        direction = 1 if distance > 0 else -1
        boost = max(8.0, min(22.0, abs(distance) * 0.4))
        self._momentum += direction * boost
        self._momentum = max(-self._max_momentum, min(self._max_momentum, self._momentum))

        current = bar.value()
        anchor = self._animation_anchor_value()
        target = anchor + distance + (self._momentum * 0.45)
        target = max(bar.minimum(), min(bar.maximum(), int(target)))

        self._animate_to(target, self._base_duration_ms, QtCore.QEasingCurve.OutCubic)
        self._settle_timer.start(150)
        event.accept()
        return True

    def _animation_anchor_value(self):
        if self._scroll_anim.state() == QtCore.QAbstractAnimation.Running:
            try:
                return int(self._scroll_anim.endValue())
            except (TypeError, ValueError):
                pass
        return self.verticalScrollBar().value()

    def _animate_to(self, target, duration_ms, easing_curve):
        bar = self.verticalScrollBar()
        current = bar.value()
        if self._scroll_anim.state() == QtCore.QAbstractAnimation.Running:
            self._scroll_anim.stop()
        self._scroll_anim.setDuration(duration_ms)
        self._scroll_anim.setEasingCurve(easing_curve)
        self._scroll_anim.setStartValue(current)
        self._scroll_anim.setEndValue(int(target))
        self._scroll_anim.start()

    def _apply_settle(self):
        bar = self.verticalScrollBar()
        if bar.maximum() <= bar.minimum():
            self._momentum = 0.0
            return

        if abs(self._momentum) < 2.4:
            self._momentum = 0.0
            return

        current = bar.value()
        extra = self._momentum * 0.55
        target = max(bar.minimum(), min(bar.maximum(), int(current + extra)))

        self._animate_to(target, self._settle_duration_ms, QtCore.QEasingCurve.OutQuart)

        self._momentum *= 0.5
        self._settle_timer.start(170)


def request_api_json(base_url: str, method: str, path: str, payload: dict = None) -> dict:
    endpoint = api_url(base_url, path)
    parsed = urllib_parse.urlparse(endpoint)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Xzen-Network API URL must start with http:// or https://")

    request_path = parsed.path or "/"
    if parsed.query:
        request_path += "?" + parsed.query

    body = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "Xzen-Online-Service",
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))

    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parsed.netloc, timeout=8)
    try:
        conn.request(method.upper(), request_path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read().decode("utf-8", errors="replace")
    finally:
        conn.close()

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {"raw": raw}

    if response.status >= 400:
        message = data.get("error") or data.get("message") or raw or response.reason
        raise RuntimeError(f"HTTP {response.status}: {message}")

    return data if isinstance(data, dict) else {"raw": data}


def load_config() -> dict:
    try:
        return xzen_service.load_waifly_config()
    except Exception as e:
        log_error(f"Failed to load Xzen-Network config: {e}")
        return {
            "api_base_url": DEFAULT_API_BASE,
            "admin_key": "",
            "user_id": "",
            "default_author": "",
        }


def save_config(config: dict):
    try:
        return xzen_service.save_waifly_config(config)
    except Exception as e:
        log_error(f"Failed to save Xzen-Network config: {e}")
        return config


def log_error(message: str):
    ensure_dirs()
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    with ONLINE_SERVICE_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")


def api_url(base_url: str, path: str) -> str:
    return clean_text(base_url).rstrip("/") + path


def build_mod_id(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", clean_text(title).lower()).strip("-")
    if not slug:
        slug = "untitled"
    return f"mod_{slug[:48]}"


def release_title(title: str) -> str:
    return clean_text(title) or "Untitled Mod"


def github_tag(mod_id: str, version: str) -> str:
    return f"{clean_text(mod_id) or 'mod_untitled'}-v{clean_text(version) or '1.0.0'}"


def release_description(
    title: str,
    author: str,
    version: str,
    description: str,
    player_id: str,
    nsfw: bool,
) -> str:
    rating = "NSFW" if nsfw else "Not NSFW"
    lines = []

    if nsfw:
        lines.extend([
            "**NSFW WARNING:** This mod pack is marked as NSFW.",
            "",
        ])

    lines.extend([
        "## Mod Details",
        f"**Author:** {clean_text(author) or 'Unknown'}",
        f"**Version:** {clean_text(version) or '1.0.0'}",
        f"**Uploader ID:** {clean_text(player_id)}",
        f"**Content Rating:** {rating}",
    ])

    body = clean_text(description)
    if body:
        lines.extend([
            "",
            "## Description",
            body,
        ])

    return "\n".join(lines)


def safe_asset_name(file_name: str) -> str:
    name = clean_text(file_name) or "mod-upload.zip"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name.lower()).strip("-")
    return safe or "mod-upload.zip"


def format_bytes(size: int) -> str:
    value = float(max(size, 0))
    for suffix in ("B", "KB", "MB", "GB"):
        if value < 1024 or suffix == "GB":
            return f"{value:.1f} {suffix}" if suffix != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


class UploadWorker(QtCore.QThread):
    log = QtCore.pyqtSignal(str)
    progress = QtCore.pyqtSignal(int)
    success = QtCore.pyqtSignal(dict)
    failure = QtCore.pyqtSignal(str)

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload

    def run(self):
        try:
            self.success.emit(self._upload())
        except Exception as e:
            message = str(e) or e.__class__.__name__
            log_error(message)
            self.failure.emit(message)

    def _upload(self) -> dict:
        file_path = Path(self.payload["file_path"])
        file_size = file_path.stat().st_size
        screenshot_paths = [
            Path(path)
            for path in self.payload.get("screenshots", [])
            if clean_text(path) and Path(path).exists()
        ]
        endpoint = api_url(self.payload["api_base_url"], "/api/admin/upload-mod")
        parsed = urllib_parse.urlparse(endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Xzen-Network API URL must start with http:// or https://")

        boundary = f"----XzenWaifly{os.getpid()}{int(QtCore.QDateTime.currentMSecsSinceEpoch())}"
        fields = {
            "id": self.payload["id"],
            "player_id": self.payload["player_id"],
            "name": self.payload["name"],
            "version": self.payload["version"],
            "author": self.payload["author"],
            "description": self.payload["description"],
            "image_url": "",
            "release_title": self.payload["release_title"],
            "mod_list_name": "",
            "nsfw": "true" if self.payload["nsfw"] else "false",
            "screenshot_assets": json.dumps(
                [safe_asset_name(path.name) for path in screenshot_paths],
                ensure_ascii=False,
            ),
        }

        field_chunks = self._field_chunks(boundary, fields)
        file_parts = [("file", file_path)] + [("screenshots", path) for path in screenshot_paths]
        file_headers = [
            self._file_header(boundary, field_name, path).encode("utf-8")
            for field_name, path in file_parts
        ]
        part_break = b"\r\n"
        file_footer = f"--{boundary}--\r\n".encode("utf-8")
        content_length = sum(len(chunk) for chunk in field_chunks)
        content_length += sum(
            len(header) + path.stat().st_size + len(part_break)
            for header, (_, path) in zip(file_headers, file_parts)
        )
        content_length += len(file_footer)
        total_file_bytes = sum(path.stat().st_size for _, path in file_parts)

        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(parsed.netloc, timeout=300)

        self.log.emit(f"Sharing {file_path.name} ({format_bytes(file_size)})")
        try:
            conn.putrequest("POST", path)
            conn.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
            conn.putheader("Content-Length", str(content_length))
            conn.putheader("X-Admin-Key", self.payload["admin_key"])
            conn.putheader("Accept", "application/json")
            conn.putheader("User-Agent", "Xzen-Mod-Manager")
            conn.endheaders()

            for chunk in field_chunks:
                conn.send(chunk)

            sent = 0
            for header, (field_name, path) in zip(file_headers, file_parts):
                conn.send(header)
                if field_name == "screenshots":
                    self.log.emit(f"Adding screenshot {path.name}")
                with path.open("rb") as handle:
                    while True:
                        chunk = handle.read(1024 * 1024)
                        if not chunk:
                            break
                        conn.send(chunk)
                        sent += len(chunk)
                        self.progress.emit(int((sent / max(total_file_bytes, 1)) * 100))
                conn.send(part_break)

            conn.send(file_footer)
            response = conn.getresponse()
            raw = response.read().decode("utf-8", errors="replace")

            try:
                data = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                data = {"raw": raw}

            if response.status >= 400:
                if isinstance(data, dict):
                    message = data.get("error") or data.get("message") or raw
                else:
                    message = raw
                raise RuntimeError(f"HTTP {response.status}: {message or response.reason}")

            self.progress.emit(100)
            self.log.emit("Xzen-Network accepted the mod.")
            return data if isinstance(data, dict) else {"raw": data}
        finally:
            conn.close()

    def _field_chunks(self, boundary: str, fields: dict) -> list:
        chunks = []
        for name, value in fields.items():
            chunk = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{clean_text(value)}\r\n"
            )
            chunks.append(chunk.encode("utf-8"))
        return chunks

    def _file_header(self, boundary: str, field_name: str, file_path: Path) -> str:
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/zip"
        asset_name = safe_asset_name(file_path.name)
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field_name}"; filename="{asset_name}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        )


class PackModsWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    success = QtCore.pyqtSignal(str, int)
    failure = QtCore.pyqtSignal(str)

    def __init__(self, user_id: str, parent=None):
        super().__init__(parent)
        self.user_id = user_id

    def run(self):
        try:
            zip_path, file_count = create_modded_zip(self.user_id, progress_callback=self.progress.emit)
            self.success.emit(str(zip_path), file_count)
        except Exception as e:
            message = str(e) or e.__class__.__name__
            log_error(message)
            self.failure.emit(message)


class FieldBlock(QtWidgets.QWidget):
    def __init__(self, label_text: str, widget: QtWidgets.QWidget, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QtWidgets.QLabel(label_text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        layout.addWidget(widget)


class OnlineServicePage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = load_config()
        self.image_paths = []
        self.pack_worker = None
        self.upload_worker = None
        self._user_id_prompt_active = False
        self.setObjectName("OnlineServiceRoot")
        self.setStyleSheet(self._qss())
        self._build_ui()
        self._apply_config()
        self._wire_preview()
        self._update_preview()
        if self.config.get("user_id_was_reset"):
            self.append_log(f"Local user ID was restored to this device ID: {self.config['user_id']}")
        elif self.config.get("identity_mode") == "account" and self.config.get("account_username"):
            self.append_log(
                f"Signed in as {self.config['account_username']} with user ID {self.config['user_id']}"
            )

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scroll = IcySmoothScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        content = QtWidgets.QWidget()
        content.setObjectName("OnlineServiceContent")
        body = QtWidgets.QVBoxLayout(content)
        body.setContentsMargins(24, 24, 24, 24)
        body.setSpacing(16)

        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(4)
        title = QtWidgets.QLabel("Share Mods")
        title.setObjectName("headerTitle")
        subtitle = QtWidgets.QLabel("Share Mod")
        subtitle.setObjectName("subTitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        body.addLayout(title_box)
        body.addWidget(self._build_form_panel())
        body.addWidget(self._build_images_panel())
        body.addWidget(self._build_share_panel())
        body.addStretch(1)

        self.scroll.setWidget(content)
        root.addWidget(self.scroll)

    def _build_form_panel(self):
        panel = self._panel()
        layout = QtWidgets.QGridLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self.title_input = QtWidgets.QLineEdit()
        self.title_input.setPlaceholderText("Mod Title")

        self.author_input = QtWidgets.QLineEdit()
        self.author_input.setPlaceholderText("Author of ModPack")

        self.version_input = QtWidgets.QLineEdit()
        self.version_input.setPlaceholderText("1.0.0")

        self.description_input = QtWidgets.QTextEdit()
        self.description_input.setPlaceholderText("Description")
        self.description_input.setFixedHeight(118)

        self.file_path_input = QtWidgets.QLineEdit()
        self.file_path_input.setReadOnly(True)
        self.file_path_input.setPlaceholderText("Pack source\\mods\\modded into a zip")

        self.file_btn = self._button("Pack Mods", "ghostBtn")
        self.file_btn.clicked.connect(self.pack_mods)

        file_row = QtWidgets.QWidget()
        file_layout = QtWidgets.QHBoxLayout(file_row)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(10)
        file_layout.addWidget(self.file_path_input, 1)
        file_layout.addWidget(self.file_btn, 0)

        self.nsfw_check = QtWidgets.QCheckBox("NSFW")
        self.nsfw_check.setObjectName("nsfwToggle")
        self.nsfw_check.setFocusPolicy(QtNoFocus)
        self.nsfw_check.setCursor(QtGui.QCursor(QtPointingHandCursor))

        layout.addWidget(FieldBlock("Mod Title:", self.title_input), 0, 0, 1, 2)
        layout.addWidget(FieldBlock("Author of ModPack:", self.author_input), 1, 0)
        layout.addWidget(FieldBlock("Version:", self.version_input), 1, 1)
        layout.addWidget(FieldBlock("Description:", self.description_input), 2, 0, 1, 2)
        layout.addWidget(FieldBlock("Packed Mods:", file_row), 3, 0, 1, 2)
        layout.addWidget(self.nsfw_check, 4, 0, 1, 2)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        return panel

    def _build_images_panel(self):
        panel = self._panel()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(10)

        label = QtWidgets.QLabel("Images")
        label.setObjectName("panelTitle")

        self.add_image_btn = self._button("Add Images", "ghostBtn")
        self.add_image_btn.clicked.connect(self.add_images)

        header.addWidget(label, 1)
        header.addWidget(self.add_image_btn, 0)

        self.image_scroll = IcySmoothScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.image_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.image_scroll.setMinimumHeight(154)

        self.image_wrap = QtWidgets.QWidget()
        self.image_grid = QtWidgets.QGridLayout(self.image_wrap)
        self.image_grid.setContentsMargins(0, 0, 0, 0)
        self.image_grid.setHorizontalSpacing(10)
        self.image_grid.setVerticalSpacing(10)
        self.image_grid.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.image_scroll.setWidget(self.image_wrap)

        layout.addLayout(header)
        layout.addWidget(self.image_scroll)
        self.refresh_images()
        return panel

    def _build_share_panel(self):
        panel = self._panel()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(12)

        self.preview_label = QtWidgets.QLabel("")
        self.preview_label.setObjectName("previewValue")
        self.preview_label.setWordWrap(True)
        self.preview_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        self.share_btn = self._button("Share Mod", "primaryBtn")
        self.share_btn.clicked.connect(self.start_share)

        row.addWidget(self.preview_label, 1)
        row.addWidget(self.share_btn, 0)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)

        self.log_output = QtWidgets.QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(120)
        self.log_output.setPlaceholderText("Share log")

        layout.addLayout(row)
        layout.addWidget(self.progress)
        layout.addWidget(self.log_output)
        return panel

    def _panel(self):
        panel = QtWidgets.QFrame()
        panel.setObjectName("panel")
        return panel

    def _button(self, text: str, object_name: str):
        button = QtWidgets.QPushButton(text)
        button.setObjectName(object_name)
        button.setMinimumHeight(28 if object_name == "tinyBtn" else 40)
        button.setFocusPolicy(QtNoFocus)
        button.setCursor(QtGui.QCursor(QtPointingHandCursor))
        return button

    def _apply_config(self):
        self.author_input.setText(self.config.get("default_author", ""))

    def _wire_preview(self):
        self.title_input.textChanged.connect(self._update_preview)
        self.version_input.textChanged.connect(self._update_preview)
        self.file_path_input.textChanged.connect(self._update_preview)

    def _update_preview(self):
        title = self.title_input.text()
        version = self.version_input.text()
        file_path = Path(clean_text(self.file_path_input.text()))
        file_size = file_path.stat().st_size if file_path.exists() else 0
        tag = github_tag(build_mod_id(title), version)
        self.preview_label.setText(
            f"{release_title(title)} | {tag} | {format_bytes(file_size)}"
        )

    def append_log(self, text: str):
        self.log_output.append(text)

    def refresh_waifly_config(self):
        fresh = load_config()
        self.config.update(fresh)

    def maybe_prompt_for_local_user_id(self):
        self.refresh_waifly_config()
        if self._user_id_prompt_active:
            return
        if not self.isVisible():
            return
        if not xzen_service.waifly_config_needs_user_id(self.config):
            return
        if self.config.get("setup_prompt_suppressed"):
            return

        self._user_id_prompt_active = True
        QtCore.QTimer.singleShot(0, self.prompt_for_local_user_id)

    def showEvent(self, event):
        super().showEvent(event)
        self.maybe_prompt_for_local_user_id()

    def prompt_for_local_user_id(self):
        self.config = xzen_service.ensure_local_user_id(parent=self, prompt=True)
        self._user_id_prompt_active = False
        if xzen_service.waifly_config_needs_user_id(self.config):
            self.append_log("Online play setup was skipped.")
            return False

        if self.config.get("identity_mode") == "account" and self.config.get("account_username"):
            self.append_log(
                f"Account {self.config['account_username']} restored user ID {self.config['user_id']}"
            )
        else:
            self.append_log(f"Local user ID ready: {self.config['user_id']}")
        return True

    def ensure_local_user_id(self) -> bool:
        if not xzen_service.waifly_config_needs_user_id(self.config):
            return True
        return self.prompt_for_local_user_id()

    def pack_mods(self):
        if self.pack_worker is not None:
            return

        user_id = clean_text(self.config.get("user_id"))
        if not user_id:
            self.append_log("Pack cancelled: missing local user ID.")
            return

        self.progress.setValue(0)
        self.append_log("Packing source\\mods\\modded...")
        self.set_busy(True)

        self.pack_worker = PackModsWorker(user_id, self)
        self.pack_worker.progress.connect(self.progress.setValue)
        self.pack_worker.success.connect(self.pack_mods_ok)
        self.pack_worker.failure.connect(self.pack_mods_failed)
        self.pack_worker.finished.connect(self.finish_pack_mods)
        self.pack_worker.start()

    def pack_mods_ok(self, zip_path: str, file_count: int):
        self.file_path_input.setText(zip_path)
        self.progress.setValue(100)
        self.append_log(f"Packed {file_count} file(s) from modded into {Path(zip_path).name}")

    def pack_mods_failed(self, message: str):
        self.progress.setValue(0)
        QtWidgets.QMessageBox.warning(self, "Pack Mods", message)

    def finish_pack_mods(self):
        self.pack_worker = None
        self.set_busy(False)

    def add_images(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Add Images",
            "",
            "Images (*.png *.jpg *.jpeg *.gif)",
        )
        changed = False
        for file_path in files:
            if file_path and file_path not in self.image_paths:
                self.image_paths.append(file_path)
                changed = True
        if changed:
            self.refresh_images()

    def remove_image(self, file_path: str):
        self.image_paths = [path for path in self.image_paths if path != file_path]
        self.refresh_images()

    def refresh_images(self):
        while self.image_grid.count():
            item = self.image_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self.image_paths:
            empty = QtWidgets.QLabel("No images added.")
            empty.setObjectName("emptyText")
            self.image_grid.addWidget(empty, 0, 0)
            return

        for index, file_path in enumerate(self.image_paths):
            card = self._image_card(file_path)
            row = index // 4
            col = index % 4
            self.image_grid.addWidget(card, row, col)

    def _image_card(self, file_path: str):
        card = QtWidgets.QFrame()
        card.setObjectName("imageCard")
        card.setFixedSize(142, 132)

        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        preview = QtWidgets.QLabel()
        preview.setObjectName("imagePreview")
        preview.setFixedSize(124, 82)
        preview.setAlignment(QtCore.Qt.AlignCenter)

        pixmap = QtGui.QPixmap(file_path)
        if pixmap.isNull():
            preview.setText("Image")
        else:
            preview.setPixmap(
                pixmap.scaled(
                    preview.size(),
                    QtCore.Qt.KeepAspectRatioByExpanding,
                    QtCore.Qt.SmoothTransformation,
                )
            )

        remove_btn = self._button("Delete", "tinyBtn")
        remove_btn.clicked.connect(lambda checked=False, path=file_path: self.remove_image(path))

        layout.addWidget(preview)
        layout.addWidget(remove_btn)
        return card

    def ensure_admin_key(self) -> bool:
        return bool(clean_text(self.config.get("admin_key")))

    def collect_payload(self):
        title = clean_text(self.title_input.text())
        author = clean_text(self.author_input.text())
        version = clean_text(self.version_input.text())
        mod_id = build_mod_id(title)
        tag = github_tag(mod_id, version)
        raw_description = clean_text(self.description_input.toPlainText())
        description = release_description(
            title=title,
            author=author,
            version=version,
            description=raw_description,
            player_id=self.config["user_id"],
            nsfw=self.nsfw_check.isChecked(),
        )
        return {
            "api_base_url": self.config.get("api_base_url", DEFAULT_API_BASE),
            "admin_key": self.config.get("admin_key", ""),
            "id": mod_id,
            "github_tag": tag,
            "player_id": self.config["user_id"],
            "name": title,
            "version": version,
            "author": author,
            "description": description,
            "raw_description": raw_description,
            "release_title": release_title(title),
            "nsfw": self.nsfw_check.isChecked(),
            "file_path": clean_text(self.file_path_input.text()),
            "screenshots": list(self.image_paths),
        }

    def validate_payload(self, payload: dict):
        missing = []
        for label, key in (
            ("Mod Title", "name"),
            ("Author of ModPack", "author"),
            ("Version", "version"),
            ("Packed Mods", "file_path"),
        ):
            if not payload[key]:
                missing.append(label)

        if missing:
            raise ValueError("Missing required fields: " + ", ".join(missing))

        file_path = Path(payload["file_path"])
        if not file_path.exists():
            raise ValueError("Selected zip file was not found.")
        if file_path.suffix.lower() != ".zip":
            raise ValueError("Selected file must be a .zip archive.")

    def set_busy(self, busy: bool):
        for widget in (
            self.share_btn,
            self.file_btn,
            self.add_image_btn,
        ):
            widget.setDisabled(busy)

    def start_share(self):
        if not self.ensure_local_user_id():
            self.append_log("Share cancelled: online play setup was skipped.")
            return

        if not self.ensure_admin_key():
            message = f"Share cancelled: missing admin key in {xzen_service.WAIFLY_CONFIG_JSON}"
            self.append_log(message)
            QtWidgets.QMessageBox.warning(self, "Share Mod", message)
            return

        self.config["default_author"] = clean_text(self.author_input.text())
        self.config = save_config(self.config)

        payload = self.collect_payload()
        try:
            self.validate_payload(payload)
        except Exception as e:
            message = str(e)
            log_error(message)
            QtWidgets.QMessageBox.warning(self, "Share Mod", message)
            return

        self.progress.setValue(0)
        self.append_log(f"Sharing {payload['name']} as {payload['player_id']}")
        self.set_busy(True)

        self.upload_worker = UploadWorker(payload, self)
        self.upload_worker.log.connect(self.append_log)
        self.upload_worker.progress.connect(self.progress.setValue)
        self.upload_worker.success.connect(self.share_ok)
        self.upload_worker.failure.connect(self.share_failed)
        self.upload_worker.finished.connect(lambda: self.set_busy(False))
        self.upload_worker.start()

    def share_ok(self, data: dict):
        download_url = data.get("download_url") or data.get("browser_download_url") or ""
        release_url = data.get("github_release_url") or data.get("release_url") or data.get("html_url") or ""
        self.append_log("Share complete.")
        if download_url:
            self.append_log(f"Download: {download_url}")
        if release_url:
            self.append_log(f"Release: {release_url}")

        message = "Mod shared successfully."
        if download_url:
            message += f"\n\nDownload URL:\n{download_url}"
        QtWidgets.QMessageBox.information(self, "Share Mod", message)
        self.reset_upload_form()

    def reset_upload_form(self):
        self.title_input.clear()
        self.version_input.clear()
        self.description_input.clear()
        self.file_path_input.clear()
        self.nsfw_check.setChecked(False)
        self.image_paths = []
        self.refresh_images()
        self.progress.setValue(0)
        self.log_output.clear()
        self.append_log("Ready for a new upload.")
        self._update_preview()

    def share_failed(self, message: str):
        log_error(message)
        self.append_log("Error: " + message)
        QtWidgets.QMessageBox.critical(
            self,
            "Share Mod",
            f"{message}\n\nSaved to:\n{ONLINE_SERVICE_LOG}",
        )

    def _qss(self):
        return f"""
        QWidget#OnlineServiceRoot,
        QWidget#OnlineServiceContent {{
            background-color: {BG_DARK};
            color: {TEXT};
        }}
        QScrollArea {{
            background-color: {BG_DARK};
            border: none;
        }}
        QFrame#panel {{
            background-color: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 8px;
        }}
        QFrame#imageCard {{
            background-color: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 8px;
        }}
        QLabel#headerTitle {{
            color: {TEXT};
            font-size: 22px;
            font-weight: 800;
            background: transparent;
        }}
        QLabel#subTitle,
        QLabel#emptyText {{
            color: {TEXT_DIM};
            font-size: 13px;
            background: transparent;
        }}
        QLabel#panelTitle {{
            color: {TEXT};
            font-size: 14px;
            font-weight: 800;
            background: transparent;
        }}
        QLabel#fieldLabel {{
            color: {TEXT_DIM};
            font-size: 11px;
            font-weight: 800;
            background: transparent;
        }}
        QLabel#userId {{
            color: {TEXT};
            background-color: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: 9px 12px;
            font-size: 12px;
            font-weight: 800;
        }}
        QLabel#previewValue {{
            color: {TEXT_DIM};
            font-size: 12px;
            font-weight: 700;
            background: transparent;
        }}
        QLabel#imagePreview {{
            color: {TEXT_DIM};
            background-color: #080808;
            border: 1px solid {BORDER};
            border-radius: 6px;
        }}
        QLineEdit,
        QTextEdit {{
            background-color: {SURFACE};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: 9px 11px;
            font-size: 12px;
            selection-background-color: #ffffff;
            selection-color: #050505;
        }}
        QLineEdit {{
            min-height: 22px;
        }}
        QLineEdit:focus,
        QTextEdit:focus {{
            border-color: {ACCENT};
            background-color: #141414;
        }}
        QCheckBox#nsfwToggle {{
            color: {TEXT};
            font-size: 13px;
            font-weight: 800;
            spacing: 8px;
            background: transparent;
        }}
        QCheckBox#nsfwToggle::indicator {{
            width: 18px;
            height: 18px;
            border: 1px solid {BORDER};
            border-radius: 4px;
            background-color: {SURFACE};
        }}
        QCheckBox#nsfwToggle::indicator:checked {{
            background-color: {TEXT};
            border-color: {ACCENT};
        }}
        QProgressBar {{
            background-color: {SURFACE};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 6px;
            min-height: 20px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background-color: {GOOD};
            border-radius: 5px;
        }}
        QPushButton#primaryBtn {{
            background-color: {TEXT};
            color: {BG_DARK};
            border: 1px solid {ACCENT};
            border-radius: 6px;
            padding: 0 16px;
            font-size: 12px;
            font-weight: 800;
        }}
        QPushButton#primaryBtn:hover {{
            background-color: #ffffff;
        }}
        QPushButton#ghostBtn,
        QPushButton#tinyBtn {{
            background-color: transparent;
            color: {TEXT_DIM};
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: 0 14px;
            font-size: 12px;
            font-weight: 800;
        }}
        QPushButton#tinyBtn {{
            min-height: 28px;
            padding: 0 8px;
            font-size: 11px;
        }}
        QPushButton#ghostBtn:hover,
        QPushButton#tinyBtn:hover {{
            color: {TEXT};
            border-color: {ACCENT};
            background-color: #121212;
        }}
        QPushButton:disabled {{
            background-color: #1b1b1b;
            color: #666666;
            border-color: #2b2b2b;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 4px 0;
        }}
        QScrollBar::handle:vertical {{
            background: #222222;
            min-height: 30px;
            border-radius: 5px;
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        """
