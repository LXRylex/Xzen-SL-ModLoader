from __future__ import annotations

import http.client
import importlib.util
import json
import re
import sys
from pathlib import Path
from urllib import parse as urllib_parse

from PyQt5 import QtCore, QtGui, QtWidgets, QtNetwork

ACCENT = "#ffffff"
BG_DARK = "#050505"
PANEL = "#0a0a0a"
TEXT = "#eeeeee"
TEXT_DIM = "#888888"
BORDER = "#333333"

GITHUB_RELEASES_API = "https://api.github.com/repos/LXRylex/xzen-online-service/releases"
SUPPORTED_ARCHIVE_SUFFIXES = (".zip", ".7z")
PLAYER_ID_PATTERN = re.compile(r"#(?:[0-9]{4}|[A-Z0-9]{8})")


def clean_text(value) -> str:
    return str(value or "").strip()


def load_xzen_service_module():
    module = sys.modules.get("xzen_service")
    if module is not None:
        return module

    module_path = Path(__file__).resolve().parents[1] / "xzen_service.py"
    spec = importlib.util.spec_from_file_location("xzen_service", str(module_path))
    if not spec or not spec.loader:
        raise ImportError(f"Unable to load xzen_service from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["xzen_service"] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


xzen_service = load_xzen_service_module()


def request_url_json(url: str) -> tuple[object, dict]:
    current_url = clean_text(url)
    parsed = urllib_parse.urlparse(current_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("URL must start with http:// or https://")

    request_path = parsed.path or "/"
    if parsed.query:
        request_path += "?" + parsed.query

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Xzen-GitHub-Mod-Browser",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parsed.netloc, timeout=20)
    try:
        conn.request("GET", request_path, headers=headers)
        response = conn.getresponse()
        raw = response.read().decode("utf-8", errors="replace")
        response_headers = {key.lower(): value for key, value in response.getheaders()}
    finally:
        conn.close()

    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {"raw": raw}

    if response.status >= 400:
        message = data.get("message") if isinstance(data, dict) else raw
        raise RuntimeError(f"HTTP {response.status}: {message or response.reason}")

    return data, response_headers


def next_link_from_header(link_header: str) -> str:
    for part in clean_text(link_header).split(","):
        section = part.strip()
        if 'rel="next"' not in section:
            continue
        match = re.search(r"<([^>]+)>", section)
        if match:
            return match.group(1)
    return ""


def extract_release_image_urls(body: str) -> list[str]:
    text = str(body or "")
    seen = set()
    urls = []
    for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text):
        url = clean_text(match.group(1))
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def extract_release_asset_image_urls(assets: list[dict]) -> list[str]:
    if not isinstance(assets, list):
        return []

    seen = set()
    urls = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        asset_name = clean_text(asset.get("name")).lower()
        if not asset_name.endswith((".gif", ".png", ".jpg", ".jpeg")):
            continue
        url = clean_text(asset.get("browser_download_url"))
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def preferred_preview_url(urls: list[str]) -> str:
    priority = [".gif", ".png", ".jpg", ".jpeg"]
    cleaned = [clean_text(url) for url in urls if clean_text(url)]
    lowered = [(url, urllib_parse.urlparse(url).path.lower()) for url in cleaned]
    for suffix in priority:
        for url, path in lowered:
            if path.endswith(suffix):
                return url
    return cleaned[0] if cleaned else ""


def parse_player_id_from_body(body: str) -> str:
    match = PLAYER_ID_PATTERN.search(clean_text(body).upper())
    return match.group(0) if match else ""


def normalize_player_id(value: str) -> str:
    normalizer = getattr(xzen_service, "normalize_player_id", None)
    if callable(normalizer):
        return clean_text(normalizer(value))

    text = clean_text(value).upper()
    if not text:
        return ""
    if not text.startswith("#"):
        text = f"#{text}"
    return text if PLAYER_ID_PATTERN.fullmatch(text) else ""


def load_friend_players() -> list[dict]:
    loader = getattr(xzen_service, "load_friends", None)
    if not callable(loader):
        return []

    try:
        players = loader()
    except Exception:
        return []
    return [item for item in players if isinstance(item, dict)]


def current_local_player_id() -> str:
    loader = getattr(xzen_service, "load_waifly_config", None)
    if not callable(loader):
        return ""

    try:
        config = loader()
    except Exception:
        return ""
    return normalize_player_id((config or {}).get("user_id"))


def find_friend_entry(player_id: str) -> dict | None:
    normalized_id = normalize_player_id(player_id)
    if not normalized_id:
        return None

    for player in load_friend_players():
        if normalize_player_id(player.get("player_id")) == normalized_id:
            return player
    return None


def mod_is_already_owned(mod: dict) -> bool:
    player_id = normalize_player_id((mod or {}).get("player_id"))
    if not player_id:
        return False
    return bool(find_friend_entry(player_id) or player_id == current_local_player_id())


def open_friendlist_tab(widget) -> bool:
    window = widget.window() if isinstance(widget, QtWidgets.QWidget) else None
    nav = getattr(window, "nav", None)
    if isinstance(nav, QtWidgets.QListWidget):
        nav.setCurrentRow(3)
        return True
    return False


def prompt_already_owned(parent, mod: dict):
    player_id = normalize_player_id(mod.get("player_id"))
    if not player_id:
        return

    friend = find_friend_entry(player_id)
    local_player_id = current_local_player_id()
    if local_player_id and player_id == local_player_id:
        message = (
            "This modpack already belongs to your current profile.\n\n"
            "Enable or load it from Friendlist instead of Community Mods."
        )
    else:
        owner_name = clean_text((friend or {}).get("display_name")) or player_id
        message = (
            f"{owner_name} is already in your Friendlist.\n\n"
            "Enable or load this modpack from Friendlist instead of Community Mods."
        )

    dialog = QtWidgets.QMessageBox(parent)
    dialog.setIcon(QtWidgets.QMessageBox.Information)
    dialog.setWindowTitle("Already Owned")
    dialog.setText(message)
    dialog.setStyleSheet(
        f"""
        QMessageBox {{
            background-color: {BG_DARK};
        }}
        QMessageBox QLabel {{
            color: {TEXT};
            font-size: 12px;
        }}
        QMessageBox QPushButton {{
            background-color: #e8e8e8;
            color: #000000;
            border: 1px solid #f4f4f4;
            border-radius: 4px;
            padding: 6px 14px;
            min-width: 132px;
            min-height: 32px;
            font-size: 11px;
            font-weight: 800;
        }}
        QMessageBox QPushButton:hover {{
            background-color: #f3f3f3;
        }}
        QMessageBox QPushButton:pressed {{
            background-color: #dcdcdc;
        }}
        """
    )
    open_btn = dialog.addButton("Open Friendlist", QtWidgets.QMessageBox.AcceptRole)
    close_btn = dialog.addButton("Close", QtWidgets.QMessageBox.RejectRole)
    open_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
    close_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
    dialog.exec_()
    if dialog.clickedButton() is open_btn:
        open_friendlist_tab(parent)


def merge_unique_urls(*groups: list[str]) -> list[str]:
    seen = set()
    merged = []
    for group in groups:
        if not isinstance(group, list):
            continue
        for url in group:
            cleaned = clean_text(url)
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            merged.append(cleaned)
    return merged


def strip_markdown_images(body: str) -> str:
    text = str(body or "")
    text = re.sub(r"!\[[^\]]*\]\(([^)]+)\)", "", text)
    text = re.sub(r"(?im)^\s*(?:#{1,6}\s*)?(?:\*\*)?screenshots?(?:\*\*)?\s*:?\s*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_bytes(size: int) -> str:
    value = max(0, int(size or 0))
    units = ["B", "KB", "MB", "GB"]
    size_float = float(value)
    for unit in units:
        if size_float < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size_float)} {unit}"
            return f"{size_float:.1f} {unit}"
        size_float /= 1024.0
    return f"{value} B"


def list_public_github_mods(max_pages: int = 5) -> list[dict]:
    mods = []
    seen = set()
    page_url = f"{GITHUB_RELEASES_API}?per_page=100"
    for _ in range(max_pages):
        data, headers = request_url_json(page_url)
        if not isinstance(data, list):
            break

        for release in data:
            if not isinstance(release, dict):
                continue

            body = clean_text(release.get("body"))
            tag = clean_text(release.get("tag_name"))
            release_title = clean_text(release.get("name")) or tag or "GitHub Release"
            release_url = clean_text(release.get("html_url"))
            player_id = parse_player_id_from_body(body)
            assets = release.get("assets", [])
            if not isinstance(assets, list):
                continue

            asset_preview_urls = extract_release_asset_image_urls(assets)
            body_preview_urls = extract_release_image_urls(body)
            screenshot_urls = merge_unique_urls(asset_preview_urls, body_preview_urls)
            preview_url = preferred_preview_url(asset_preview_urls) or preferred_preview_url(body_preview_urls)

            for asset in assets:
                if not isinstance(asset, dict):
                    continue

                asset_name = clean_text(asset.get("name"))
                lower_asset_name = asset_name.lower()
                download_url = clean_text(asset.get("browser_download_url"))
                if not lower_asset_name.endswith(SUPPORTED_ARCHIVE_SUFFIXES) or not download_url:
                    continue

                identity = (tag, asset_name, download_url)
                if identity in seen:
                    continue
                seen.add(identity)

                mods.append(
                    {
                        "id": tag or Path(asset_name).stem,
                        "name": release_title,
                        "release_title": release_title,
                        "version": tag,
                        "player_id": player_id,
                        "description": body,
                        "download_url": download_url,
                        "file_name": asset_name,
                        "file_size": int(asset.get("size") or 0),
                        "github_release_url": release_url,
                        "github_tag": tag,
                        "preview_url": preview_url,
                        "screenshot_urls": screenshot_urls,
                    }
                )

        page_url = next_link_from_header(headers.get("link", ""))
        if not page_url:
            break

    return mods


class GitHubModsWorker(QtCore.QThread):
    succeeded = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)

    def run(self):
        try:
            self.succeeded.emit(list_public_github_mods())
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)


class SmoothScrollArea(QtWidgets.QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scroll_anim = QtCore.QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._scroll_anim.setDuration(320)
        self._scroll_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._wheel_step = 70
        self._momentum = 0
        self._max_momentum = 300
        self._settle_timer = QtCore.QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.timeout.connect(self._apply_settle)

    def wheelEvent(self, event):
        bar = self.verticalScrollBar()
        angle = event.angleDelta().y()
        if angle == 0:
            event.ignore()
            return
        direction = -1 if angle > 0 else 1
        self._momentum += direction * 28
        self._momentum = max(-self._max_momentum, min(self._max_momentum, self._momentum))
        current = bar.value()
        target = current + (direction * self._wheel_step) + self._momentum
        target = max(bar.minimum(), min(bar.maximum(), target))
        if self._scroll_anim.state() == QtCore.QAbstractAnimation.Running:
            self._scroll_anim.stop()
        self._scroll_anim.setStartValue(current)
        self._scroll_anim.setEndValue(target)
        self._scroll_anim.start()
        self._settle_timer.start(90)
        event.accept()

    def _apply_settle(self):
        bar = self.verticalScrollBar()
        if self._momentum == 0:
            return
        extra = int(self._momentum * 0.45)
        if abs(extra) < 2:
            self._momentum = 0
            return
        current = bar.value()
        target = current + extra
        target = max(bar.minimum(), min(bar.maximum(), target))
        if self._scroll_anim.state() == QtCore.QAbstractAnimation.Running:
            self._scroll_anim.stop()
        self._scroll_anim.setDuration(260)
        self._scroll_anim.setEasingCurve(QtCore.QEasingCurve.OutQuart)
        self._scroll_anim.setStartValue(current)
        self._scroll_anim.setEndValue(target)
        self._scroll_anim.start()
        self._momentum = int(self._momentum * 0.35)
        self._settle_timer.start(70)


class RemotePreviewFrame(QtWidgets.QFrame):
    _network_manager = None

    def __init__(self, preview_url: str = "", parent=None, frame_size: QtCore.QSize | None = None):
        super().__init__(parent)
        self.preview_url = clean_text(preview_url)
        self._reply = None
        self._movie = None
        self._buffer = None
        self._pixmap_data = b""
        self._frame_size = frame_size or QtCore.QSize(132, 92)
        self._scaled_movie_size = QtCore.QSize(
            max(1, self._frame_size.width() - 2),
            max(1, self._frame_size.height() - 2),
        )
        if RemotePreviewFrame._network_manager is None:
            RemotePreviewFrame._network_manager = QtNetwork.QNetworkAccessManager()

        self.setFixedSize(self._frame_size)
        self.setObjectName("modPreviewFrame")
        self.setStyleSheet(
            f"""
            QFrame#modPreviewFrame {{
                background-color: #0d0d0d;
                border: none;
                border-radius: 10px;
            }}
            """
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.label = QtWidgets.QLabel("")
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(self.label)

        if self.preview_url:
            self._load_preview()
        else:
            self.label.setText("No Preview")
            self.label.setStyleSheet(f"border: none; background: transparent; color: {TEXT_DIM}; font-size: 11px;")

    def _load_preview(self):
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(self.preview_url))
        request.setHeader(QtNetwork.QNetworkRequest.UserAgentHeader, "Xzen-GitHub-Mod-Browser")
        follow_redirect_attr = getattr(QtNetwork.QNetworkRequest, "FollowRedirectsAttribute", None)
        if follow_redirect_attr is not None:
            request.setAttribute(follow_redirect_attr, True)
        redirect_policy_attr = getattr(QtNetwork.QNetworkRequest, "RedirectPolicyAttribute", None)
        no_less_safe_policy = getattr(QtNetwork.QNetworkRequest, "NoLessSafeRedirectPolicy", None)
        if redirect_policy_attr is not None and no_less_safe_policy is not None:
            request.setAttribute(redirect_policy_attr, no_less_safe_policy)
        self._reply = RemotePreviewFrame._network_manager.get(request)
        self._reply.finished.connect(self._on_preview_loaded)

    def _on_preview_loaded(self):
        reply = self._reply
        self._reply = None
        if reply is None:
            return
        try:
            if reply.error() != QtNetwork.QNetworkReply.NoError:
                return
            data = bytes(reply.readAll())
            if not data:
                return
            path = urllib_parse.urlparse(self.preview_url).path.lower()
            if path.endswith(".gif"):
                self._buffer = QtCore.QBuffer(self)
                self._buffer.setData(QtCore.QByteArray(data))
                self._buffer.open(QtCore.QIODevice.ReadOnly)
                self._movie = QtGui.QMovie(self._buffer, b"gif", self)
                self._movie.setScaledSize(self._scaled_movie_size)
                self.label.setMovie(self._movie)
                self._movie.start()
                return
            pixmap = QtGui.QPixmap()
            if pixmap.loadFromData(data):
                self._pixmap_data = data
                self._update_static_pixmap()
        finally:
            reply.deleteLater()

    def _update_static_pixmap(self):
        if not self._pixmap_data:
            return
        pixmap = QtGui.QPixmap()
        if not pixmap.loadFromData(self._pixmap_data):
            return
        target = self.label.size()
        self.label.setPixmap(
            pixmap.scaled(
                target,
                QtCore.Qt.KeepAspectRatioByExpanding,
                QtCore.Qt.SmoothTransformation,
            )
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._scaled_movie_size = self.label.size()
        if self._movie is not None:
            self._movie.setScaledSize(self._scaled_movie_size)
        elif self._pixmap_data:
            self._update_static_pixmap()


class ModDetailsDialog(QtWidgets.QDialog):
    install_requested = QtCore.pyqtSignal(object)

    def __init__(self, mod: dict, parent=None):
        super().__init__(parent)
        self.mod = mod
        self._already_owned = mod_is_already_owned(mod)
        self.setWindowTitle(clean_text(mod.get("release_title")) or "GitHub Mod")
        self.setModal(True)
        self.setFixedSize(760, 560)
        self.setStyleSheet(f"QDialog {{ background-color: {BG_DARK}; color: {TEXT}; }}")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QtWidgets.QLabel(clean_text(mod.get("release_title")) or clean_text(mod.get("name")) or "Untitled")
        title.setStyleSheet(f"color: {TEXT}; font-size: 20px; font-weight: 800;")
        layout.addWidget(title)

        meta = QtWidgets.QLabel(
            f"Version: {clean_text(mod.get('version')) or 'unknown'}   "
            f"File: {clean_text(mod.get('file_name')) or 'unknown'}   "
            f"Size: {format_bytes(int(mod.get('file_size') or 0))}"
        )
        meta.setWordWrap(True)
        meta.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        layout.addWidget(meta)

        content_scroll = SmoothScrollArea()
        content_scroll.setWidgetResizable(True)
        content_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        content_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        content_scroll.setStyleSheet(
            f"""
            QScrollArea {{
                background-color: {PANEL};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {PANEL};
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
            QScrollBar::handle:vertical:hover {{
                background: #333333;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            """
        )

        content_wrap = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_wrap)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(12)

        description = QtWidgets.QTextBrowser()
        description.setOpenExternalLinks(True)
        description.setStyleSheet(
            f"""
            QTextBrowser {{
                background-color: {PANEL};
                color: {TEXT};
                border: none;
                padding: 0px;
                font-size: 12px;
            }}
            """
        )
        description.setMarkdown(strip_markdown_images(clean_text(mod.get("description"))) or "No description provided.")
        description.setMinimumHeight(220)
        content_layout.addWidget(description)

        screenshot_urls = mod.get("screenshot_urls") if isinstance(mod.get("screenshot_urls"), list) else []
        if screenshot_urls:
            screenshots_title = QtWidgets.QLabel("Screenshots")
            screenshots_title.setStyleSheet(f"color: {TEXT}; font-size: 16px; font-weight: 700;")
            content_layout.addWidget(screenshots_title)

            screenshots_wrap = QtWidgets.QWidget()
            screenshots_grid = QtWidgets.QGridLayout(screenshots_wrap)
            screenshots_grid.setContentsMargins(0, 0, 0, 0)
            screenshots_grid.setHorizontalSpacing(12)
            screenshots_grid.setVerticalSpacing(12)

            for index, screenshot_url in enumerate(screenshot_urls):
                row = index // 2
                col = index % 2
                frame = RemotePreviewFrame(
                    screenshot_url,
                    screenshots_wrap,
                    frame_size=QtCore.QSize(330, 186),
                )
                screenshots_grid.addWidget(frame, row, col)

            content_layout.addWidget(screenshots_wrap)

        content_layout.addStretch(1)
        content_scroll.setWidget(content_wrap)
        layout.addWidget(content_scroll, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        close_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        close_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_DIM};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {TEXT};
                border-color: {TEXT};
            }}
            """
        )

        release_btn = QtWidgets.QPushButton("Already Added" if self._already_owned else "Install")
        release_btn.setToolTip(
            "Open Friendlist for this sharer."
            if self._already_owned
            else "Install this mod and add the sharer to Friendlist."
        )
        release_btn.clicked.connect(self.handle_primary_action)
        release_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        release_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {"transparent" if self._already_owned else TEXT};
                color: {TEXT if self._already_owned else BG_DARK};
                border: 1px solid {BORDER if self._already_owned else ACCENT};
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {"#141414" if self._already_owned else "#ffffff"};
                border-color: {ACCENT};
            }}
            """
        )

        btn_row.addWidget(close_btn)
        btn_row.addWidget(release_btn)
        layout.addLayout(btn_row)

    def open_release(self):
        url = clean_text(self.mod.get("github_release_url"))
        if url:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def handle_primary_action(self):
        if self._already_owned:
            prompt_already_owned(self, self.mod)
            return
        self.install_requested.emit(self.mod)
        self.accept()


class GitHubModCard(QtWidgets.QFrame):
    details_requested = QtCore.pyqtSignal(object)
    install_requested = QtCore.pyqtSignal(object)

    def __init__(self, mod: dict, parent=None):
        super().__init__(parent)
        self.mod = mod
        self._already_owned = mod_is_already_owned(mod)
        self.setFixedSize(190, 246)
        self.setObjectName("githubModCard")
        self.setStyleSheet(
            f"""
            QFrame#githubModCard {{
                background-color: {PANEL};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
            QFrame#githubModCard:hover {{
                border: 1px solid {ACCENT};
                background-color: #101010;
            }}
            """
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        self.preview = RemotePreviewFrame(
            clean_text(mod.get("preview_url")),
            self,
            frame_size=QtCore.QSize(178, 122),
        )
        layout.addWidget(self.preview, 0, QtCore.Qt.AlignHCenter)
        layout.addSpacing(8)

        title = QtWidgets.QLabel(clean_text(mod.get("release_title")) or clean_text(mod.get("name")) or "Untitled")
        title.setWordWrap(True)
        title.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        title.setFixedHeight(40)
        title.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        layout.addWidget(title)

        layout.addStretch(1)

        bottom_row = QtWidgets.QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(6)

        details_btn = QtWidgets.QPushButton("Details")
        details_btn.setFixedHeight(24)
        details_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        details_btn.clicked.connect(lambda: self.details_requested.emit(self.mod))
        details_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {TEXT};
                color: {BG_DARK};
                border: 1px solid {ACCENT};
                border-radius: 5px;
                padding: 0px 10px;
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #ffffff;
            }}
            """
        )

        release_btn = QtWidgets.QPushButton("Already Added" if self._already_owned else "Install")
        release_btn.setFixedHeight(24)
        release_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        release_btn.setToolTip(
            "Open Friendlist for this sharer."
            if self._already_owned
            else "Install this mod and add the sharer to Friendlist."
        )
        release_btn.clicked.connect(self.handle_primary_action)
        release_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 5px;
                padding: 0px 10px;
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                border-color: {ACCENT};
                background-color: {"#141414" if self._already_owned else "transparent"};
            }}
            """
        )

        bottom_row.addWidget(details_btn, 1)
        bottom_row.addWidget(release_btn, 1)
        layout.addLayout(bottom_row)

    def open_release(self):
        url = clean_text(self.mod.get("github_release_url"))
        if url:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def handle_primary_action(self):
        if self._already_owned:
            prompt_already_owned(self, self.mod)
            return
        self.install_requested.emit(self.mod)


class GitHubModsPage(QtWidgets.QWidget):
    GRID_COLUMNS = 4

    def __init__(self):
        super().__init__()
        self.worker = None
        self.all_mods: list[dict] = []
        self.filtered_mods: list[dict] = []
        self.card_widgets: list[QtWidgets.QWidget] = []
        self._setup_ui()
        self.refresh_mods()

    def _setup_ui(self):
        self.setStyleSheet(f"QWidget {{ background-color: {BG_DARK}; color: {TEXT}; }}")

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        header_row = QtWidgets.QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        title_col = QtWidgets.QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(3)

        title = QtWidgets.QLabel("GitHub Mods")
        title.setStyleSheet(f"color: {TEXT}; font-size: 18px; font-weight: 700;")
        subtitle = QtWidgets.QLabel("Install public GitHub mod releases directly into the Friendlist system.")
        subtitle.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        header_row.addLayout(title_col, 1)

        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.setMinimumHeight(38)
        self.refresh_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.refresh_btn.clicked.connect(self.refresh_mods)
        self.refresh_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {PANEL};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 0 16px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                border-color: {ACCENT};
            }}
            QPushButton:disabled {{
                color: #555555;
                border-color: #333333;
            }}
            """
        )
        header_row.addWidget(self.refresh_btn, 0)

        root.addLayout(header_row)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(10)
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Search mod title, version, file, or description...")
        self.search_input.setMinimumHeight(42)
        self.search_input.textChanged.connect(self.apply_filter)
        self.search_input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {PANEL};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 0 14px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {ACCENT};
                background-color: #101010;
            }}
            """
        )
        search_row.addWidget(self.search_input, 1)
        root.addLayout(search_row)

        self.status_label = QtWidgets.QLabel("Loading public GitHub mods...")
        self.status_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; background: transparent;")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.gallery_scroll = SmoothScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.gallery_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.gallery_scroll.setStyleSheet(
            f"""
            QScrollArea {{
                border: none;
                background-color: {BG_DARK};
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {BG_DARK};
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
            QScrollBar::handle:vertical:hover {{
                background: #333333;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            """
        )

        self.gallery_wrap = QtWidgets.QWidget()
        self.gallery_wrap.setStyleSheet(f"QWidget {{ background-color: {BG_DARK}; }}")
        self.gallery_layout = QtWidgets.QGridLayout(self.gallery_wrap)
        self.gallery_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery_layout.setHorizontalSpacing(14)
        self.gallery_layout.setVerticalSpacing(14)
        self.gallery_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)

        self.gallery_scroll.setWidget(self.gallery_wrap)
        root.addWidget(self.gallery_scroll, 1)

    def showEvent(self, event):
        super().showEvent(event)
        if self.all_mods:
            self.render_gallery()

    def clear_gallery(self):
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.card_widgets.clear()

    def refresh_mods(self):
        if self.worker is not None:
            return
        self.refresh_btn.setEnabled(False)
        self.status_label.setText("Loading public GitHub mods...")
        self.worker = GitHubModsWorker(self)
        self.worker.succeeded.connect(self.on_mods_loaded)
        self.worker.failed.connect(self.on_mods_failed)
        self.worker.finished.connect(self._clear_worker)
        self.worker.start()

    def _clear_worker(self):
        self.worker = None
        self.refresh_btn.setEnabled(True)

    def on_mods_loaded(self, mods):
        self.all_mods = [mod for mod in mods if isinstance(mod, dict)]
        self.apply_filter()

    def on_mods_failed(self, message: str):
        self.all_mods = []
        self.filtered_mods = []
        self.clear_gallery()
        self.status_label.setText(f"Could not load GitHub mods: {message}")

    def apply_filter(self):
        query = clean_text(self.search_input.text()).lower()
        if not query:
            self.filtered_mods = list(self.all_mods)
        else:
            filtered = []
            for mod in self.all_mods:
                haystack = " ".join(
                    [
                        clean_text(mod.get("release_title")),
                        clean_text(mod.get("name")),
                        clean_text(mod.get("version")),
                        clean_text(mod.get("file_name")),
                        clean_text(mod.get("description")),
                    ]
                ).lower()
                if query in haystack:
                    filtered.append(mod)
            self.filtered_mods = filtered
        self.render_gallery()

    def render_gallery(self):
        self.clear_gallery()
        if not self.filtered_mods:
            empty = QtWidgets.QLabel("No GitHub mods matched your search.")
            empty.setStyleSheet(f"color: {TEXT_DIM}; font-size: 13px; padding: 18px 0;")
            self.gallery_layout.addWidget(empty, 0, 0)
            if self.all_mods:
                self.status_label.setText(f"Showing 0 of {len(self.all_mods)} public GitHub mods.")
            else:
                self.status_label.setText("No public GitHub mods were found.")
            return

        for index, mod in enumerate(self.filtered_mods):
            row = index // self.GRID_COLUMNS
            col = index % self.GRID_COLUMNS
            card = GitHubModCard(mod, self.gallery_wrap)
            card.details_requested.connect(self.open_mod_details)
            card.install_requested.connect(self.install_mod)
            self.gallery_layout.addWidget(card, row, col)
            self.card_widgets.append(card)

        self.status_label.setText(
            f"Showing {len(self.filtered_mods)} of {len(self.all_mods)} public GitHub mods."
        )

    def open_mod_details(self, mod: dict):
        dialog = ModDetailsDialog(mod, self)
        dialog.install_requested.connect(self.install_mod)
        dialog.exec_()

    def _service_page(self):
        window = self.window() if isinstance(self, QtWidgets.QWidget) else None
        page = getattr(window, "page_service", None)
        return page if page is not None and hasattr(page, "install_community_mod") else None

    def install_mod(self, mod: dict):
        if not isinstance(mod, dict):
            return

        if mod_is_already_owned(mod):
            prompt_already_owned(self, mod)
            self.status_label.setText("This sharer is already in your Friendlist.")
            return

        service_page = self._service_page()
        if service_page is None:
            self.status_label.setText("Friendlist service is not available right now.")
            QtWidgets.QMessageBox.warning(self, "Install Failed", "Friendlist service is not available right now.")
            return

        player_id = normalize_player_id(mod.get("player_id"))
        if not player_id:
            self.status_label.setText("This mod is missing a valid player ID.")
            QtWidgets.QMessageBox.warning(self, "Install Failed", "This mod is missing a valid player ID.")
            return

        base_url = ""
        waifly_config = getattr(service_page, "waifly_config", {})
        if isinstance(waifly_config, dict):
            base_url = clean_text(waifly_config.get("api_base_url"))
        sharer_name = ""
        if base_url and hasattr(xzen_service, "resolve_player_display_name"):
            try:
                sharer_name = clean_text(
                    xzen_service.resolve_player_display_name(
                        base_url,
                        player_id,
                        friends=getattr(service_page, "players", []),
                    )
                )
            except Exception:
                sharer_name = ""

        success, message = service_page.install_community_mod(mod, display_name=sharer_name)
        self.status_label.setText(message)
        if success:
            self.render_gallery()
