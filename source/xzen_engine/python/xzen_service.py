from PyQt5 import QtWidgets, QtCore, QtGui, QtNetwork
from pathlib import Path
from urllib import parse as urllib_parse
import hashlib
import http.client
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time
import json
import uuid
import zipfile

try:
    import winreg
except ImportError:
    winreg = None

ACCENT   = "#ffffff"
BG_DARK  = "#050505"
PANEL    = "#0a0a0a"
TEXT     = "#eeeeee"
TEXT_DIM = "#888888"
BORDER   = "#333333"
PLAYER_ID_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PLAYER_ID_BODY_LENGTH = 8


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(os.path.abspath(os.path.dirname(__file__))).parent.parent.parent


BASE_DIR = app_root()
USER_DATA_DIR = BASE_DIR / "source" / "profile" / "user_data"
MODS_DIR = BASE_DIR / "source" / "mods"
ONLINE_PROFILES_DIR = MODS_DIR / "online_profiles"
ONLINE_RUNTIME_DIR = MODS_DIR / "online_runtime"
ONLINE_RUNTIME_BACKUP_DIR = ONLINE_RUNTIME_DIR / "backup"
BATS_DIR = BASE_DIR / "source" / "xzen_engine" / "bats"
LAUNCH_BAT = BATS_DIR / "launch_game.bat"
FRIENDS_JSON = USER_DATA_DIR / "friend_list.json"
WAIFLY_CONFIG_JSON = USER_DATA_DIR / "waifly_upload_config.json"
WAIFLY_ACCOUNTS_JSON = USER_DATA_DIR / "waifly_accounts.json"
ONLINE_RUNTIME_STATE_JSON = USER_DATA_DIR / "online_runtime_state.json"
PATHS_JSON = USER_DATA_DIR / "paths.json"
DEFAULT_API_BASE = "http://node.waifly.com:28183"
DEFAULT_ADMIN_KEY = "5minLabs2022"
GITHUB_RELEASES_API = "https://api.github.com/repos/LXRylex/xzen-online-service/releases"
ACCOUNT_USERNAME_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9._-]{1,22}[a-z0-9])?")
ACCOUNT_PASSWORD_MIN_LENGTH = 6
ACCOUNT_ID_NAMESPACE = "xzen-waifly-account-v1"
ACCOUNT_HASH_NAMESPACE = "xzen-waifly-password-v1"
STEAM_APP_ID = 1352080
GAME_HINTS = ("smash", "legend")


def ensure_dirs():
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    ONLINE_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


HELPERS_DIR = Path(__file__).resolve().with_suffix("")


def _load_helper_module(module_name: str):
    module_path = HELPERS_DIR / f"{module_name}.py"
    spec_name = f"_xzen_service_{module_name}"
    spec = importlib.util.spec_from_file_location(spec_name, str(module_path))
    if not spec or not spec.loader:
        raise ImportError(f"Unable to load xzen_service helper: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec_name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


_identity_helpers = _load_helper_module("identity_helpers")
clean_text = _identity_helpers.clean_text
normalize_player_id = _identity_helpers.normalize_player_id
normalize_identity_mode = _identity_helpers.normalize_identity_mode
normalize_account_username = _identity_helpers.normalize_account_username
display_account_name = _identity_helpers.display_account_name
validate_account_credentials = _identity_helpers.validate_account_credentials
account_password_hash = _identity_helpers.account_password_hash
derive_account_user_id = _identity_helpers.derive_account_user_id
utc_now_iso = _identity_helpers.utc_now_iso
base36_encode = _identity_helpers.base36_encode
read_windows_machine_guid = _identity_helpers.read_windows_machine_guid
device_fingerprint = _identity_helpers.device_fingerprint
generate_user_id = _identity_helpers.generate_user_id

_paths_helpers = _load_helper_module("paths_helpers").PathsHelper(
    paths_json=PATHS_JSON,
    steam_app_id=STEAM_APP_ID,
    game_hints=GAME_HINTS,
    ensure_dirs=ensure_dirs,
)
save_paths_config = _paths_helpers.save_paths_config
discover_game_paths = _paths_helpers.discover_game_paths
ensure_paths_config = _paths_helpers.ensure_paths_config

_storage_helpers = _load_helper_module("storage_helpers").StorageHelper(
    friends_json=FRIENDS_JSON,
    waifly_accounts_json=WAIFLY_ACCOUNTS_JSON,
    ensure_dirs=ensure_dirs,
    clean_text=clean_text,
    normalize_player_id=normalize_player_id,
    normalize_account_username=normalize_account_username,
    validate_account_credentials=validate_account_credentials,
    account_password_hash=account_password_hash,
    utc_now_iso=utc_now_iso,
    device_fingerprint=device_fingerprint,
    normalize_identity_mode=normalize_identity_mode,
)
normalize_friend_entries = _storage_helpers.normalize_friend_entries
load_local_accounts = _storage_helpers.load_local_accounts
save_local_accounts = _storage_helpers.save_local_accounts
remember_local_account = _storage_helpers.remember_local_account
set_local_account_avatar = _storage_helpers.set_local_account_avatar
set_local_account_friends = _storage_helpers.set_local_account_friends
restore_local_account_friends = _storage_helpers.restore_local_account_friends
set_local_account_password = _storage_helpers.set_local_account_password

load_paths_config = _paths_helpers.load_paths_config
game_exe_path = _paths_helpers.game_exe_path
game_assetbundles_dir = _paths_helpers.game_assetbundles_dir
game_ui_target_path = _paths_helpers.game_ui_target_path
default_stage_destinations = _paths_helpers.default_stage_destinations


def load_friends():
    return _storage_helpers.load_friends()


def save_friends(players):
    return _storage_helpers.save_friends(players, current_config_loader=load_waifly_config)


def clear_active_friends():
    return _storage_helpers.clear_active_friends()


_ui_helpers = _load_helper_module("ui_helpers").UiHelpers(
    bg_dark=BG_DARK,
    text=TEXT,
)
format_mod_count_label = _ui_helpers.format_mod_count_label
style_compact_message_box = _ui_helpers.style_compact_message_box
show_compact_message_box = _ui_helpers.show_compact_message_box
show_compact_warning = _ui_helpers.show_compact_warning
show_compact_information = _ui_helpers.show_compact_information
show_compact_question = _ui_helpers.show_compact_question


def preferred_account_user_id(config: dict, existing_account: dict | None = None, base_url: str = DEFAULT_API_BASE) -> str:
    existing_account = existing_account if isinstance(existing_account, dict) else {}
    candidates = [
        normalize_player_id(existing_account.get("user_id")),
        normalize_player_id((config or {}).get("user_id")),
        normalize_player_id((config or {}).get("device_user_id")),
    ]
    for candidate in candidates:
        if candidate:
            return candidate

    return normalize_player_id(generate_available_user_id(base_url)) or normalize_player_id(generate_user_id())


def configure_account_identity(config: dict, username: str, password: str, *, mode: str) -> dict:
    normalized_username, password_text = validate_account_credentials(username, password)
    normalized_mode = clean_text(mode).lower()
    password_hash_value = account_password_hash(normalized_username, password_text)
    local_accounts = load_local_accounts()
    existing = local_accounts.get(normalized_username)
    base_url = clean_text((config or {}).get("api_base_url")) or DEFAULT_API_BASE
    candidate_user_id = preferred_account_user_id(config, existing, base_url)

    if normalized_mode == "create":
        if not candidate_user_id:
            raise ValueError("Could not determine a valid player ID for this account.")
        remote = create_remote_account(base_url, normalized_username, password_hash_value, candidate_user_id)
        stored_account_secret = password_hash_value
    elif normalized_mode == "login":
        remote = login_remote_account(base_url, normalized_username, password_hash_value, password_text)
        stored_account_secret = clean_text(remote.get("_used_password_hash")) or password_hash_value
    else:
        raise ValueError(f"Unsupported account mode: {mode}")

    user_id = normalize_player_id(remote.get("user_id")) or candidate_user_id

    next_config = dict(config or {})
    next_config.update({
        "online_play_enabled": True,
        "identity_mode": "account",
        "account_username": normalized_username,
        "account_password_hash": stored_account_secret,
        "account_avatar_path": clean_text(existing.get("avatar_path")) if isinstance(existing, dict) else "",
        "user_id": user_id,
    })
    saved = save_waifly_config(next_config)
    remember_local_account(normalized_username, saved["user_id"], stored_account_secret)
    restored_friends = normalize_friend_entries(existing.get("friends")) if isinstance(existing, dict) else []
    if restored_friends:
        save_friends(restored_friends)
    saved["account_created_local"] = not bool(existing)
    return saved


def base36_encode(number: int) -> str:
    if number <= 0:
        return "0"

    chars = []
    value = number
    while value:
        value, remainder = divmod(value, 36)
        chars.append(PLAYER_ID_ALPHABET[remainder])
    return "".join(reversed(chars))


def read_windows_machine_guid() -> str:
    if winreg is None:
        return ""

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return clean_text(value)
    except Exception:
        return ""


def device_fingerprint() -> str:
    parts = [
        read_windows_machine_guid(),
        clean_text(os.environ.get("COMPUTERNAME")),
        clean_text(os.environ.get("PROCESSOR_IDENTIFIER")),
        f"{uuid.getnode():012x}",
    ]
    source = "|".join(part for part in parts if part)
    if not source:
        source = "xzen-service-device"
    return hashlib.sha256(source.encode("utf-8", errors="replace")).hexdigest()


def generate_user_id() -> str:
    fingerprint = device_fingerprint()
    encoded = base36_encode(int(fingerprint, 16)).upper()
    body = encoded[-PLAYER_ID_BODY_LENGTH:].rjust(PLAYER_ID_BODY_LENGTH, "0")
    return f"#{body}"


def save_waifly_config(config: dict) -> dict:
    ensure_dirs()
    api_base_url = clean_text(config.get("api_base_url")) or DEFAULT_API_BASE
    admin_key = clean_text(config.get("admin_key")) or DEFAULT_ADMIN_KEY
    online_play_enabled = bool(config.get("online_play_enabled"))
    device_print = device_fingerprint()
    device_user_id = generate_user_id()
    identity_mode = normalize_identity_mode(config.get("identity_mode"))
    account_username = normalize_account_username(config.get("account_username"))
    account_hash = clean_text(config.get("account_password_hash"))
    account_avatar_path = clean_text(config.get("account_avatar_path"))
    setup_prompt_suppressed = bool(config.get("setup_prompt_suppressed"))

    if not online_play_enabled:
        user_id = ""
        identity_mode = "device"
        account_username = ""
        account_hash = ""
        account_avatar_path = ""
    elif identity_mode == "account":
        user_id = normalize_player_id(config.get("user_id"))
        if not user_id or not account_username:
            identity_mode = "device"
            user_id = device_user_id
            account_username = ""
            account_hash = ""
            account_avatar_path = ""
    else:
        user_id = device_user_id
        account_avatar_path = ""

    payload = {
        "api_base_url": api_base_url,
        "user_id": user_id,
        "admin_key": admin_key,
        "default_author": clean_text(config.get("default_author")),
        "online_play_enabled": online_play_enabled,
        "device_fingerprint": device_print,
        "device_user_id": device_user_id,
        "identity_mode": identity_mode,
        "account_username": account_username,
        "account_password_hash": account_hash,
        "account_avatar_path": account_avatar_path,
        "setup_prompt_suppressed": bool(setup_prompt_suppressed and not user_id),
    }
    WAIFLY_CONFIG_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    result = payload.copy()
    result["needs_user_id_generation"] = not online_play_enabled
    return result


def load_waifly_config() -> dict:
    ensure_dirs()
    defaults = {
        "api_base_url": DEFAULT_API_BASE,
        "user_id": "",
        "admin_key": DEFAULT_ADMIN_KEY,
        "default_author": "",
        "online_play_enabled": False,
        "identity_mode": "device",
        "account_username": "",
        "account_password_hash": "",
        "account_avatar_path": "",
        "setup_prompt_suppressed": False,
    }

    if not WAIFLY_CONFIG_JSON.exists():
        return save_waifly_config(defaults)

    try:
        raw = json.loads(WAIFLY_CONFIG_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[xzen_service] failed to load Xzen-Network config: {e}")
        return save_waifly_config(defaults)

    if not isinstance(raw, dict):
        return save_waifly_config(defaults)

    raw_user_id = normalize_player_id(raw.get("user_id"))
    identity_mode = normalize_identity_mode(raw.get("identity_mode") if "identity_mode" in raw else ("account" if clean_text(raw.get("account_username")) else "device"))
    account_username = normalize_account_username(raw.get("account_username"))
    local_accounts = load_local_accounts()
    existing_account = local_accounts.get(account_username, {}) if account_username else {}
    config = {
        "api_base_url": clean_text(raw.get("api_base_url")) or DEFAULT_API_BASE,
        "user_id": raw_user_id,
        "admin_key": clean_text(raw.get("admin_key")) or DEFAULT_ADMIN_KEY,
        "default_author": clean_text(raw.get("default_author")),
        "online_play_enabled": bool(raw.get("online_play_enabled")) or bool(raw_user_id),
        "identity_mode": identity_mode,
        "account_username": account_username,
        "account_password_hash": clean_text(raw.get("account_password_hash")),
        "account_avatar_path": clean_text(raw.get("account_avatar_path")) or clean_text(existing_account.get("avatar_path")),
        "setup_prompt_suppressed": bool(raw.get("setup_prompt_suppressed")),
    }
    saved = save_waifly_config(config)
    saved["user_id_was_reset"] = bool(
        saved["online_play_enabled"]
        and saved.get("identity_mode") == "device"
        and raw_user_id
        and raw_user_id != saved["user_id"]
    )
    return saved


def waifly_config_needs_user_id(config: dict) -> bool:
    return (not bool(config.get("online_play_enabled"))) or (not bool(normalize_player_id(config.get("user_id"))))


def api_url(base_url: str, path: str) -> str:
    return clean_text(base_url).rstrip("/") + path


def request_json(base_url: str, method: str, path: str, payload: dict = None, extra_headers: dict = None) -> dict:
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
        "User-Agent": "Xzen-Service",
    }
    if extra_headers:
        headers.update({str(key): str(value) for key, value in extra_headers.items() if value is not None})
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))

    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parsed.netloc, timeout=15)
    try:
        conn.request(method.upper(), request_path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read().decode("utf-8", errors="replace")
    finally:
        conn.close()

    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {"raw": raw}

    if response.status >= 400:
        if isinstance(data, dict):
            message = data.get("error") or data.get("message") or raw or response.reason
        else:
            message = raw or response.reason
        raise RuntimeError(f"HTTP {response.status}: {message}")

    return data if isinstance(data, dict) else {"raw": data}


def create_remote_account(base_url: str, username: str, password_hash_value: str, user_id: str) -> dict:
    return request_json(
        base_url,
        "POST",
        "/api/accounts/create",
        {
            "username": normalize_account_username(username),
            "password_hash": clean_text(password_hash_value),
            "user_id": normalize_player_id(user_id),
        },
    )


def login_payload_variants(username: str, password_hash_value: str, raw_password: str = "") -> list[dict]:
    normalized_username = normalize_account_username(username)
    variants = []
    seen = set()

    def add_variant(password_value: str):
        candidate = clean_text(password_value)
        if not normalized_username or not candidate:
            return
        if candidate in seen:
            return
        seen.add(candidate)
        variants.append({
            "username": normalized_username,
            "password_hash": candidate,
        })

    add_variant(password_hash_value)

    local_accounts = load_local_accounts()
    existing = local_accounts.get(normalized_username, {})
    if isinstance(existing, dict):
        add_variant(existing.get("password_hash"))

    add_variant(raw_password)
    return variants


def login_remote_account(base_url: str, username: str, password_hash_value: str, raw_password: str = "") -> dict:
    variants = login_payload_variants(username, password_hash_value, raw_password)
    last_error = None

    for payload in variants:
        try:
            result = request_json(
                base_url,
                "POST",
                "/api/accounts/login",
                payload,
            )
            if isinstance(result, dict):
                result["_used_password_hash"] = clean_text(payload.get("password_hash"))
            return result
        except Exception as e:
            last_error = e
            continue

    if last_error is not None:
        raise last_error

    raise RuntimeError("Could not build a valid login request.")


def format_wait_time(seconds: int) -> str:
    remaining = max(0, int(seconds))
    hours, remainder = divmod(remaining, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


class GitHubRateLimitError(RuntimeError):
    def __init__(self, message: str, reset_at: int | None = None, secondary: bool = False):
        super().__init__(message)
        self.reset_at = reset_at
        self.secondary = secondary


def github_rate_limit_details(status: int, response_headers: dict, api_message: str) -> dict:
    message = clean_text(api_message)
    message_lower = message.lower()
    remaining = clean_text(response_headers.get("x-ratelimit-remaining"))
    retry_after = clean_text(response_headers.get("retry-after"))
    reset_raw = clean_text(response_headers.get("x-ratelimit-reset"))

    is_rate_limited = (
        status in (403, 429)
        and (
            "rate limit" in message_lower
            or remaining == "0"
            or bool(retry_after)
        )
    )
    if not is_rate_limited:
        return {}

    reset_at = int(reset_raw) if reset_raw.isdigit() else None
    if retry_after.isdigit() and reset_at is None:
        reset_at = int(time.time()) + int(retry_after)
    if reset_at is None:
        reset_at = int(time.time()) + 60

    is_secondary = "secondary rate limit" in message_lower
    parts = ["GitHub is rate limiting this IP right now."]
    if is_secondary:
        parts.append("It looks like a secondary rate limit.")

    wait_seconds = max(0, int(reset_at) - int(time.time()))
    parts.append(f"Mods should be available again in {format_wait_time(wait_seconds)}.")

    if message:
        parts.append(f"GitHub message: {message}")
    return {
        "message": " ".join(parts),
        "reset_at": reset_at,
        "secondary": is_secondary,
    }


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
        "User-Agent": "Xzen-Service",
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
        rate_limit = github_rate_limit_details(response.status, response_headers, message or response.reason)
        if rate_limit:
            raise GitHubRateLimitError(
                rate_limit["message"],
                reset_at=rate_limit.get("reset_at"),
                secondary=bool(rate_limit.get("secondary")),
            )
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


def strip_markdown_images(body: str) -> str:
    text = str(body or "")
    text = re.sub(r"!\[[^\]]*\]\(([^)]+)\)", "", text)
    text = re.sub(r"(?im)^\s*(?:#{1,6}\s*)?(?:\*\*)?screenshots?(?:\*\*)?\s*:?\s*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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
    if not isinstance(urls, list):
        return ""

    priority = [".gif", ".png", ".jpg", ".jpeg"]
    cleaned = [clean_text(url) for url in urls if clean_text(url)]
    lowered = [(url, urllib_parse.urlparse(url).path.lower()) for url in cleaned]

    for suffix in priority:
        for url, path in lowered:
            if path.endswith(suffix):
                return url

    return cleaned[0] if cleaned else ""


def check_player_id_exists(base_url: str, player_id: str) -> dict:
    encoded_id = urllib_parse.quote(player_id, safe="")
    return request_json(base_url, "GET", f"/api/players/exists/{encoded_id}")


def check_account_exists(base_url: str, username: str) -> dict:
    encoded_username = urllib_parse.quote(normalize_account_username(username), safe="")
    return request_json(base_url, "GET", f"/api/accounts/exists/{encoded_username}")


def lookup_account_username(base_url: str, username: str) -> dict:
    encoded_username = urllib_parse.quote(normalize_account_username(username), safe="")
    return request_json(base_url, "GET", f"/api/accounts/lookup/{encoded_username}")


def lookup_account_by_player_id(base_url: str, player_id: str) -> dict:
    encoded_player_id = urllib_parse.quote(normalize_player_id(player_id), safe="")
    last_error = None
    for path in (
        f"/api/accounts/lookup-by-id/{encoded_player_id}",
        f"/api/accounts/lookup-by-user-id/{encoded_player_id}",
    ):
        try:
            return request_json(base_url, "GET", path)
        except Exception as e:
            last_error = e
            continue
    if last_error is not None:
        raise last_error
    return {}


def register_player_id(base_url: str, player_id: str) -> dict:
    return request_json(base_url, "POST", "/api/players/register-id", {"player_id": player_id})


def player_id_exists(base_url: str, player_id: str) -> bool:
    data = check_player_id_exists(base_url, player_id)
    return bool(data.get("exists") or data.get("already_exists"))


def generate_available_user_id(base_url: str = DEFAULT_API_BASE, max_attempts: int = 50) -> str:
    candidate = generate_user_id()
    try:
        result = register_player_id(base_url, candidate)
        return normalize_player_id(result.get("player_id")) or candidate
    except Exception as e:
        print(f"[xzen_service] failed to register generated player ID {candidate}: {e}")
        return candidate


def resolve_friend_search(base_url: str, query: str) -> dict:
    raw_query = clean_text(query)
    player_id = normalize_player_id(raw_query)
    if player_id:
        payload = {}
        try:
            payload = check_player_id_exists(base_url, player_id)
        except Exception:
            payload = {}

        payload = payload.copy() if isinstance(payload, dict) else {}
        registry_exists = bool(payload.get("exists") or payload.get("already_exists"))
        account_username = normalize_account_username(payload.get("username"))
        if not account_username:
            try:
                account_lookup = lookup_account_by_player_id(base_url, player_id)
            except Exception:
                account_lookup = {}
            account_username = normalize_account_username(
                account_lookup.get("username")
                or account_lookup.get("account_username")
            )
        payload["exists"] = True
        payload["player_id"] = normalize_player_id(payload.get("player_id") or player_id) or player_id
        payload["username"] = account_username
        payload["direct_player_id"] = True
        payload["registry_exists"] = registry_exists
        return payload

    username = normalize_account_username(raw_query)
    if not username:
        raise RuntimeError("Enter a valid username or player ID.")

    exists_payload = check_account_exists(base_url, username)
    exists = bool(exists_payload.get("exists")) if isinstance(exists_payload, dict) else False
    if not exists:
        return {
            "exists": False,
            "username": username,
            "player_id": "",
        }

    lookup_payload = lookup_account_username(base_url, username)
    player_id = normalize_player_id(lookup_payload.get("user_id"))
    return {
        "exists": bool(player_id),
        "username": username,
        "player_id": player_id,
    }


def list_player_mods(base_url: str, player_id: str) -> list[dict]:
    encoded_id = urllib_parse.quote(player_id, safe="")
    data = request_json(base_url, "GET", f"/api/mods/?player_id={encoded_id}")
    mods = data.get("mods", [])
    return [item for item in mods if isinstance(item, dict)] if isinstance(mods, list) else []


def normalize_server_mod(mod: dict, player_id: str) -> dict:
    item = mod.copy()
    screenshots = item.get("screenshot_urls", [])
    screenshot_urls = [clean_text(url) for url in screenshots if clean_text(url)] if isinstance(screenshots, list) else []
    item["player_id"] = normalize_player_id(item.get("player_id") or player_id)
    item["screenshot_urls"] = screenshot_urls
    item["preview_url"] = clean_text(item.get("preview_url")) or preferred_preview_url(screenshot_urls)
    return item


def fetch_player_mods(base_url: str, player_id: str) -> list[dict]:
    normalized_id = normalize_player_id(player_id)
    merged = []
    seen = set()
    github_error = None
    server_error = None

    def add_mods(items):
        for mod in items:
            if not isinstance(mod, dict):
                continue
            identity = mod_identity(mod)
            if identity and identity in seen:
                continue
            if identity:
                seen.add(identity)
            merged.append(mod)

    try:
        add_mods(list_github_release_mods(normalized_id))
    except GitHubRateLimitError:
        raise
    except Exception as e:
        github_error = e

    try:
        add_mods(
            normalize_server_mod(mod, normalized_id)
            for mod in list_player_mods(base_url, normalized_id)
            if isinstance(mod, dict)
        )
    except Exception as e:
        server_error = e

    if merged:
        return merged
    if github_error is not None:
        raise github_error
    if server_error is not None:
        raise server_error
    return []


def resolve_player_display_name(base_url: str, player_id: str, friends: list[dict] | None = None) -> str:
    normalized_id = normalize_player_id(player_id)
    if not normalized_id:
        return ""

    for player in friends or []:
        if normalize_player_id(player.get("player_id")) != normalized_id:
            continue

        display_name = clean_text(player.get("display_name"))
        if display_name and display_name != normalized_id:
            return display_name

        account_username = normalize_account_username(player.get("account_username"))
        if account_username:
            return display_account_name(account_username)

    try:
        account_lookup = lookup_account_by_player_id(base_url, normalized_id)
    except Exception:
        account_lookup = {}

    username = normalize_account_username(
        account_lookup.get("username")
        or account_lookup.get("account_username")
    )
    if username:
        return display_account_name(username)

    return normalized_id


def delete_shared_mod(base_url: str, admin_key: str, mod: dict) -> dict:
    payload = {
        "id": clean_text(mod.get("id")),
        "player_id": normalize_player_id(mod.get("player_id")),
        "github_tag": clean_text(mod.get("github_tag")),
        "release_title": clean_text(mod.get("release_title")) or clean_text(mod.get("name")),
    }
    if not payload["player_id"]:
        raise ValueError("This shared mod does not have a valid player ID.")
    if not payload["github_tag"] and not payload["id"]:
        raise ValueError("This shared mod does not have a valid GitHub tag.")
    if not clean_text(admin_key):
        raise ValueError("Missing admin key for deleting the shared mod.")

    result = request_json(
        base_url,
        "POST",
        "/api/admin/delete-mod",
        payload,
        extra_headers={"X-Admin-Key": clean_text(admin_key)},
    )
    if not isinstance(result, dict):
        raise RuntimeError("Delete mod returned an unexpected response.")
    if not result.get("ok", True):
        raise RuntimeError(clean_text(result.get("error")) or "Delete mod failed.")
    return result


def list_github_release_mods(player_id: str, max_pages: int = 5) -> list[dict]:
    normalized_id = normalize_player_id(player_id)
    if not normalized_id:
        return []

    mods = []
    page_url = f"{GITHUB_RELEASES_API}?per_page=100"
    for _ in range(max_pages):
        data, headers = request_url_json(page_url)
        if not isinstance(data, list):
            break

        for release in data:
            if not isinstance(release, dict):
                continue

            body = clean_text(release.get("body"))
            if normalized_id not in body:
                continue

            tag = clean_text(release.get("tag_name"))
            release_title = clean_text(release.get("name")) or tag or "GitHub Release"
            release_url = clean_text(release.get("html_url"))
            assets = release.get("assets", [])
            if not isinstance(assets, list):
                continue
            asset_preview_urls = extract_release_asset_image_urls(assets)
            body_preview_urls = extract_release_image_urls(body)
            screenshot_urls = asset_preview_urls or body_preview_urls
            preview_url = preferred_preview_url(asset_preview_urls) or preferred_preview_url(body_preview_urls)

            for asset in assets:
                if not isinstance(asset, dict):
                    continue

                asset_name = clean_text(asset.get("name"))
                download_url = clean_text(asset.get("browser_download_url"))
                if not asset_name.lower().endswith(".zip") or not download_url:
                    continue

                mods.append({
                    "id": tag or Path(asset_name).stem,
                    "name": release_title,
                    "version": tag,
                    "author": clean_text(release.get("author", {}).get("login") if isinstance(release.get("author"), dict) else ""),
                    "player_id": normalized_id,
                    "description": body,
                    "download_url": download_url,
                    "file_name": asset_name,
                    "file_size": int(asset.get("size") or 0),
                    "github_asset_name": asset_name,
                    "github_release_url": release_url,
                    "github_tag": tag,
                    "release_title": release_title,
                    "nsfw": "NSFW" in body.upper(),
                    "screenshot_urls": screenshot_urls,
                    "preview_url": preview_url,
                })

        page_url = next_link_from_header(headers.get("link", ""))
        if not page_url:
            break

    return mods


def safe_folder_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9#._-]+", "-", clean_text(value)).strip(".- ")
    return name or "unknown"


def safe_file_name(value: str, default: str = "mod.zip") -> str:
    name = Path(clean_text(value)).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".- ")
    return name or default


def copy_player_id_to_clipboard(player_id: str, parent=None):
    normalized_id = normalize_player_id(player_id)
    if not normalized_id:
        return

    QtWidgets.QApplication.clipboard().setText(normalized_id)
    if parent is not None:
        QtWidgets.QToolTip.showText(
            QtGui.QCursor.pos(),
            f"Copied ID: {normalized_id}",
            parent,
        )


def prompt_for_online_play_user_id(parent=None) -> dict | None:
    dialog = OnlinePlaySetupDialog(parent=parent)
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        return None
    return getattr(dialog, "result_config", None)


def ensure_local_user_id(parent=None, prompt: bool = False) -> dict:
    config = load_waifly_config()
    if not waifly_config_needs_user_id(config):
        return config

    if prompt:
        prompted_config = prompt_for_online_play_user_id(parent)
        if not isinstance(prompted_config, dict):
            config["setup_prompt_suppressed"] = True
            return save_waifly_config(config)
        return prompted_config

    config["online_play_enabled"] = True
    return save_waifly_config(config)


def update_account_avatar(config: dict, avatar_path: str) -> dict:
    current = dict(config or {})
    username = normalize_account_username(current.get("account_username"))
    if normalize_identity_mode(current.get("identity_mode")) != "account" or not username:
        return load_waifly_config()

    current["account_avatar_path"] = clean_text(avatar_path)
    set_local_account_avatar(username, avatar_path)
    return save_waifly_config(current)


def logout_account_identity(config: dict) -> dict:
    current = dict(config or {})
    username = normalize_account_username(current.get("account_username"))
    if username:
        set_local_account_friends(username, load_friends())
    current.update({
        "online_play_enabled": False,
        "identity_mode": "device",
        "account_username": "",
        "account_password_hash": "",
        "account_avatar_path": "",
        "user_id": "",
    })
    saved = save_waifly_config(current)
    clear_active_friends()
    return saved


def describe_waifly_error(message: str) -> str:
    text = clean_text(message)
    lower = text.lower()
    if "account already exists" in lower:
        return "That username is already taken on Xzen-Network."
    if "account not found" in lower:
        return "That account was not found on Xzen-Network."
    if "invalid credentials" in lower:
        return "The username or password was incorrect."
    if "username, password_hash, and user_id are required" in lower:
        return "Account creation failed because Xzen Mod Manager did not send a valid player ID."
    if "username and password_hash are required" in lower:
        return "Log in failed because the account request was missing the username or password hash."
    if "Shared_Data/player_ids.json" in text and "Failed to decode repo JSON" in text:
        return (
            "Xzen-Network could not register the player ID because its server file "
            "`Shared_Data/player_ids.json` is not valid JSON."
        )
    if (
        "getaddrinfo failed" in lower
        or "name or service not known" in lower
        or "nodename nor servname provided" in lower
    ):
        return (
            "The app could not resolve the server address. This usually means your internet "
            "connection, DNS, or the server hostname is unavailable right now."
        )
    return text


def online_profile_dir(player_id: str) -> Path:
    return ONLINE_PROFILES_DIR / safe_folder_name(player_id)


def online_profile_has_content(player_id: str) -> bool:
    profile_dir = online_profile_dir(player_id)
    if not profile_dir.exists() or not profile_dir.is_dir():
        return False
    return any(path.is_file() and path.suffix.lower() == ".zip" for path in profile_dir.iterdir())


def load_online_profile_manifest(player_id: str) -> dict:
    profile_dir = online_profile_dir(player_id)
    manifest_path = profile_dir / "manifest.json"
    default_manifest = {
        "player_id": player_id,
        "mods": [],
        "skipped": [],
    }
    if not manifest_path.exists():
        return default_manifest

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return default_manifest

    if not isinstance(raw, dict):
        return default_manifest

    mods = raw.get("mods", [])
    skipped = raw.get("skipped", [])
    return {
        "player_id": clean_text(raw.get("player_id")) or player_id,
        "mods": [item for item in mods if isinstance(item, dict)] if isinstance(mods, list) else [],
        "skipped": [item for item in skipped if isinstance(item, dict)] if isinstance(skipped, list) else [],
    }


def save_online_profile_manifest(player_id: str, manifest: dict):
    profile_dir = online_profile_dir(player_id)
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def delete_online_profile(player_id: str):
    profile_dir = online_profile_dir(player_id)
    if profile_dir.exists() and profile_dir.is_dir():
        shutil.rmtree(profile_dir)


def mod_identity(mod: dict) -> str:
    return (
        clean_text(mod.get("github_tag"))
        or clean_text(mod.get("id"))
        or clean_text(mod.get("download_url"))
        or clean_text(mod.get("name"))
    )


def iter_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return [path for path in root.rglob("*") if path.is_file()]


def load_online_runtime_state() -> dict:
    if not ONLINE_RUNTIME_STATE_JSON.exists():
        return {}

    try:
        raw = json.loads(ONLINE_RUNTIME_STATE_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}

    return raw if isinstance(raw, dict) else {}


def save_online_runtime_state(state: dict):
    ensure_dirs()
    ONLINE_RUNTIME_STATE_JSON.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def clear_online_runtime_state():
    if ONLINE_RUNTIME_STATE_JSON.exists():
        ONLINE_RUNTIME_STATE_JSON.unlink()


def normalize_online_runtime_path(path_text: str) -> str:
    path_value = clean_text(path_text)
    if not path_value:
        return ""
    return os.path.normcase(os.path.normpath(path_value))


def normalize_active_online_runtime_mod(active: dict) -> dict | None:
    if not isinstance(active, dict):
        return None

    files = []
    for item in active.get("files", []):
        if not isinstance(item, dict):
            continue
        target_path = clean_text(item.get("target_path"))
        if not target_path:
            continue
        files.append(
            {
                "category": clean_text(item.get("category")),
                "target_path": target_path,
                "backup_path": clean_text(item.get("backup_path")),
                "had_original": bool(item.get("had_original")),
            }
        )

    if not files:
        return None

    return {
        "player_id": normalize_player_id(active.get("player_id")),
        "mod_identity": clean_text(active.get("mod_identity")),
        "mod_title": clean_text(active.get("mod_title")),
        "backup_root": clean_text(active.get("backup_root")),
        "extracted_dir": clean_text(active.get("extracted_dir")),
        "files": files,
    }


def active_online_runtime_mods() -> list[dict]:
    state = load_online_runtime_state()
    raw_mods = state.get("active_mods")
    normalized: list[dict] = []
    if isinstance(raw_mods, list):
        for item in raw_mods:
            normalized_item = normalize_active_online_runtime_mod(item)
            if normalized_item is not None:
                normalized.append(normalized_item)
        return normalized

    legacy_active = normalize_active_online_runtime_mod(state.get("active_mod"))
    return [legacy_active] if legacy_active is not None else []


def save_active_online_runtime_mods(active_mods: list[dict]):
    normalized_mods = []
    for item in active_mods:
        normalized_item = normalize_active_online_runtime_mod(item)
        if normalized_item is not None:
            normalized_mods.append(normalized_item)

    if not normalized_mods:
        clear_online_runtime_state()
        return

    save_online_runtime_state({"active_mods": normalized_mods})


def active_online_runtime_mod() -> dict:
    active_mods = active_online_runtime_mods()
    return active_mods[-1].copy() if active_mods else {}


def active_online_runtime_mods_for_player(player_id: str) -> list[dict]:
    normalized_player_id = normalize_player_id(player_id)
    if not normalized_player_id:
        return []
    return [
        active.copy()
        for active in active_online_runtime_mods()
        if normalize_player_id(active.get("player_id")) == normalized_player_id
    ]


def is_online_mod_active(player_id: str, mod: dict) -> bool:
    normalized_player_id = normalize_player_id(player_id)
    identity = mod_identity(mod)
    if not normalized_player_id or not identity:
        return False
    return any(
        normalize_player_id(active.get("player_id")) == normalized_player_id
        and clean_text(active.get("mod_identity")) == identity
        for active in active_online_runtime_mods()
    )


def is_game_running() -> bool:
    if sys.platform != "win32":
        return False

    exe_name = game_exe_path().name
    if not exe_name:
        return False

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    result = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
        timeout=15,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}".lower()
    if result.returncode != 0:
        raise RuntimeError(f"Could not check whether {exe_name} is running.")
    return exe_name.lower() in output and "no tasks are running" not in output


def restart_game_if_running() -> bool:
    if not is_game_running():
        return False

    if not LAUNCH_BAT.exists():
        raise FileNotFoundError(f"launch_game.bat was not found at {LAUNCH_BAT}")

    cmd_exe = os.environ.get("ComSpec", "cmd.exe")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    proc = subprocess.Popen(
        [cmd_exe, "/c", str(LAUNCH_BAT)],
        cwd=str(LAUNCH_BAT.parent),
        creationflags=creationflags,
    )
    if not proc or not proc.pid:
        raise RuntimeError("Could not start launch_game.bat.")
    return True


def find_manifest_mod(player_id: str, mod: dict) -> tuple[dict, list[dict], int, dict]:
    identity = mod_identity(mod)
    if not identity:
        raise FileNotFoundError("This mod does not have a valid identity.")

    manifest = load_online_profile_manifest(player_id)
    manifest_mods = [item.copy() for item in manifest.get("mods", []) if isinstance(item, dict)]
    for index, item in enumerate(manifest_mods):
        if mod_identity(item) == identity:
            return manifest, manifest_mods, index, item.copy()

    raise FileNotFoundError("This mod is not installed locally yet.")


def save_manifest_mod(player_id: str, manifest: dict, manifest_mods: list[dict], index: int, mod: dict):
    manifest_mods[index] = mod.copy()
    save_online_profile_manifest(
        player_id,
        {
            "player_id": clean_text(manifest.get("player_id")) or player_id,
            "mods": manifest_mods,
            "skipped": [item for item in manifest.get("skipped", []) if isinstance(item, dict)],
        },
    )


def extracted_mod_folder_name(mod: dict) -> str:
    title = (
        clean_text(mod.get("release_title"))
        or clean_text(mod.get("name"))
        or clean_text(mod.get("id"))
        or "online-mod"
    )
    identity = mod_identity(mod) or title
    digest = hashlib.sha1(identity.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f"{safe_folder_name(title)}-{digest}"


def find_modded_dir(root: Path) -> Path | None:
    direct = root / "modded"
    if direct.exists() and direct.is_dir():
        return direct

    candidates = sorted(
        [path for path in root.rglob("modded") if path.is_dir()],
        key=lambda path: len(path.parts),
    )
    return candidates[0] if candidates else None


def ensure_online_mod_extracted(player_id: str, mod: dict) -> tuple[dict, Path]:
    manifest, manifest_mods, index, stored_mod = find_manifest_mod(player_id, mod)
    local_file = clean_text(stored_mod.get("local_file"))
    if not local_file:
        raise FileNotFoundError("This mod does not have a saved local zip.")

    profile_dir = online_profile_dir(player_id)
    zip_path = profile_dir / local_file
    if not zip_path.exists():
        raise FileNotFoundError(f"Installed zip was not found: {zip_path}")

    extracted_dir_name = clean_text(stored_mod.get("extracted_dir")) or extracted_mod_folder_name(stored_mod)
    extracted_root = profile_dir / extracted_dir_name
    extracted_modded = extracted_root / "modded"
    if extracted_modded.exists() and extracted_modded.is_dir():
        return stored_mod, extracted_modded

    temp_root = profile_dir / f".extract-{safe_folder_name(extracted_dir_name)}"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    ensure_dir(temp_root)

    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(temp_root)

        found_modded = find_modded_dir(temp_root)
        if found_modded is None:
            raise RuntimeError(f"{zip_path.name} does not contain a modded folder.")

        if extracted_root.exists():
            shutil.rmtree(extracted_root)
        ensure_dir(extracted_root)
        shutil.move(str(found_modded), str(extracted_modded))
    finally:
        if temp_root.exists():
            shutil.rmtree(temp_root)

    stored_mod["extracted_dir"] = extracted_dir_name
    save_manifest_mod(player_id, manifest, manifest_mods, index, stored_mod)
    return stored_mod, extracted_modded


def add_online_plan_entry(plan: list[dict], category: str, source: Path, target: Path, backup_rel: Path):
    plan.append(
        {
            "category": category,
            "source_path": str(source),
            "target_path": str(target),
            "backup_rel": backup_rel.as_posix(),
        }
    )


def build_online_mod_apply_plan(modded_dir: Path) -> list[dict]:
    assetbundles_dir = game_assetbundles_dir()
    if not assetbundles_dir.exists():
        raise FileNotFoundError(f"AssetBundles folder was not found: {assetbundles_dir}")

    plan: list[dict] = []

    characters_dir = modded_dir / "characters"
    if characters_dir.exists():
        for source in iter_files(characters_dir):
            rel = source.relative_to(characters_dir)
            if source.name in {"user.logs", "_summary.log"} or source.suffix.lower() == ".txt":
                continue
            add_online_plan_entry(
                plan,
                "characters",
                source,
                assetbundles_dir / "characters" / rel,
                Path("characters") / rel,
            )

    emoticon_dir = modded_dir / "emoticon"
    if emoticon_dir.exists():
        for source in iter_files(emoticon_dir):
            rel = source.relative_to(emoticon_dir)
            if source.name in {"user.logs", "_summary.log"} or source.suffix.lower() == ".txt":
                continue
            add_online_plan_entry(
                plan,
                "emoticon",
                source,
                assetbundles_dir / "emoticon" / rel,
                Path("emoticon") / rel,
            )

    ui_dir = modded_dir / "ui_mods"
    if ui_dir.exists():
        ui_files = [
            source for source in sorted(iter_files(ui_dir), key=lambda path: path.as_posix().lower())
            if source.name not in {"user.logs", "_summary.log"} and source.suffix.lower() != ".txt"
        ]
        if ui_files:
            ui_target = game_ui_target_path(assetbundles_dir)
            add_online_plan_entry(
                plan,
                "ui_mods",
                ui_files[0],
                ui_target,
                Path("ui_mods") / "ui_original",
            )

    custom_stages_dir = modded_dir / "custom_stages"
    if custom_stages_dir.exists():
        default_scenes_dir, default_mods_dir = default_stage_destinations(assetbundles_dir)
        stage_entries = [path for path in sorted(custom_stages_dir.iterdir(), key=lambda path: path.name.lower()) if path.is_dir()]
        if not stage_entries:
            stage_entries = [custom_stages_dir]

        for stage_root in stage_entries:
            scenes_dir = default_scenes_dir
            mods_dir = default_mods_dir
            stage_name = safe_folder_name(stage_root.name or "stage")
            for source in iter_files(stage_root):
                lower_name = source.name.lower()
                if lower_name in {"destination.json", "user.logs", "_summary.log"} or source.suffix.lower() == ".txt":
                    continue
                if lower_name == "chartrial02":
                    add_online_plan_entry(
                        plan,
                        "custom_stages",
                        source,
                        scenes_dir / source.name,
                        Path("custom_stages") / "scenes" / stage_name / source.name,
                    )
                elif lower_name.endswith(".ress"):
                    add_online_plan_entry(
                        plan,
                        "custom_stages",
                        source,
                        mods_dir / source.name,
                        Path("custom_stages") / "mods" / stage_name / source.name,
                    )

    return plan


def _restore_online_runtime_mod(active: dict):
    files = [item for item in active.get("files", []) if isinstance(item, dict)]
    for item in reversed(files):
        target_path = Path(clean_text(item.get("target_path")))
        had_original = bool(item.get("had_original"))
        backup_path_text = clean_text(item.get("backup_path"))
        if had_original:
            if not backup_path_text:
                raise RuntimeError(f"Restore data is missing for {target_path}.")
            backup_path = Path(backup_path_text)
            if not backup_path.exists():
                raise RuntimeError(f"Restore backup was not found: {backup_path}")
            ensure_dir(target_path.parent)
            shutil.copy2(backup_path, target_path)
        elif target_path.exists():
            target_path.unlink()

    backup_root_text = clean_text(active.get("backup_root"))
    if backup_root_text:
        backup_root = Path(backup_root_text)
        if backup_root.exists():
            shutil.rmtree(backup_root)


def disable_active_online_mod(player_id: str | None = None, mod: dict | None = None) -> dict | None:
    active_mods = active_online_runtime_mods()
    if not active_mods:
        return None

    normalized_player_id = normalize_player_id(player_id or "")
    identity = mod_identity(mod) if isinstance(mod, dict) else ""

    target_index = -1
    for index in range(len(active_mods) - 1, -1, -1):
        active = active_mods[index]
        if normalized_player_id and normalize_player_id(active.get("player_id")) != normalized_player_id:
            continue
        if identity and clean_text(active.get("mod_identity")) != identity:
            continue
        target_index = index
        break

    if target_index < 0:
        if normalized_player_id or identity:
            return None
        target_index = len(active_mods) - 1

    active = active_mods[target_index]
    _restore_online_runtime_mod(active)
    del active_mods[target_index]
    save_active_online_runtime_mods(active_mods)
    return active


def disable_all_active_online_mods(player_id: str | None = None) -> list[dict]:
    restored_mods: list[dict] = []
    normalized_player_id = normalize_player_id(player_id or "")
    while True:
        restored = disable_active_online_mod(player_id=normalized_player_id or None)
        if not restored:
            break
        restored_mods.append(restored)
    return restored_mods


def format_online_mod_conflicts(mod_title: str, conflicts: list[dict]) -> str:
    lines = [
        f"Cannot load {mod_title} because it would replace files from another loaded modpack.",
        "",
        "Conflicting files:",
    ]
    for item in conflicts[:8]:
        target_path = clean_text(item.get("target_path"))
        file_name = Path(target_path).name if target_path else "unknown file"
        conflict_title = clean_text(item.get("mod_title")) or "loaded mod"
        conflict_player = normalize_player_id(item.get("player_id")) or "unknown player"
        lines.append(f"- {file_name} from {conflict_title} ({conflict_player})")
    remaining = len(conflicts) - 8
    if remaining > 0:
        lines.append(f"- plus {remaining} more conflicting file(s)")
    lines.extend(
        [
            "",
            "Disable the conflicting loaded mod first, then try again.",
        ]
    )
    return "\n".join(lines)


def find_online_mod_conflicts(plan: list[dict], active_mods: list[dict], player_id: str, identity: str) -> list[dict]:
    active_targets: dict[str, dict] = {}
    normalized_player_id = normalize_player_id(player_id)
    clean_identity = clean_text(identity)

    for active in active_mods:
        if (
            normalize_player_id(active.get("player_id")) == normalized_player_id
            and clean_text(active.get("mod_identity")) == clean_identity
        ):
            continue
        for item in active.get("files", []):
            if not isinstance(item, dict):
                continue
            target_key = normalize_online_runtime_path(item.get("target_path"))
            if target_key and target_key not in active_targets:
                active_targets[target_key] = active

    conflicts: list[dict] = []
    seen_targets: set[str] = set()
    for entry in plan:
        target_key = normalize_online_runtime_path(entry.get("target_path"))
        if not target_key or target_key in seen_targets or target_key not in active_targets:
            continue
        active = active_targets[target_key]
        conflicts.append(
            {
                "target_path": clean_text(entry.get("target_path")),
                "player_id": clean_text(active.get("player_id")),
                "mod_title": clean_text(active.get("mod_title")),
                "mod_identity": clean_text(active.get("mod_identity")),
            }
        )
        seen_targets.add(target_key)
    return conflicts


def toggle_online_mod_load(player_id: str, mod: dict, allow_replace: bool = False) -> dict:
    player_id = normalize_player_id(player_id)
    if not player_id:
        raise RuntimeError("Invalid player ID.")

    identity = mod_identity(mod)
    if not identity:
        raise RuntimeError("This mod does not have a valid identity.")

    mod_title = clean_text(mod.get("release_title")) or clean_text(mod.get("name")) or "selected mod"
    if is_online_mod_active(player_id, mod):
        restored = disable_active_online_mod(player_id=player_id, mod=mod) or {}
        return {
            "action": "disabled",
            "message": f"Disabled {clean_text(restored.get('mod_title')) or mod_title} and restored the previous game files.",
        }

    active_mods = active_online_runtime_mods()
    stored_mod, extracted_modded = ensure_online_mod_extracted(player_id, mod)
    plan = build_online_mod_apply_plan(extracted_modded)
    if not plan:
        raise RuntimeError("This mod did not contain any supported files to load.")

    conflicts = find_online_mod_conflicts(plan, active_mods, player_id, identity)
    if conflicts:
        if allow_replace:
            seen_conflicts: set[tuple[str, str]] = set()
            replaced_titles: list[str] = []
            for item in conflicts:
                conflict_player = normalize_player_id(item.get("player_id"))
                conflict_identity = clean_text(item.get("mod_identity"))
                if not conflict_player or not conflict_identity:
                    continue
                conflict_key = (conflict_player, conflict_identity)
                if conflict_key in seen_conflicts:
                    continue
                seen_conflicts.add(conflict_key)
                restored = disable_active_online_mod(
                    player_id=conflict_player,
                    mod={"id": conflict_identity},
                )
                if restored:
                    replaced_titles.append(
                        clean_text(restored.get("mod_title")) or conflict_player
                    )
            active_mods = active_online_runtime_mods()
        else:
            return {
                "action": "conflict",
                "message": format_online_mod_conflicts(mod_title, conflicts),
                "conflicts": conflicts,
            }
    else:
        replaced_titles = []

    backup_root = ONLINE_RUNTIME_BACKUP_DIR / f"{safe_folder_name(player_id)}-{hashlib.sha1(identity.encode('utf-8', errors='replace')).hexdigest()[:8]}"
    if backup_root.exists():
        shutil.rmtree(backup_root)
    ensure_dir(backup_root)

    applied_files = []
    try:
        for entry in plan:
            source_path = Path(entry["source_path"])
            target_path = Path(entry["target_path"])
            backup_path = backup_root / entry["backup_rel"]
            had_original = target_path.exists()

            if had_original:
                ensure_dir(backup_path.parent)
                shutil.copy2(target_path, backup_path)

            ensure_dir(target_path.parent)
            shutil.copy2(source_path, target_path)
            applied_files.append(
                {
                    "category": entry["category"],
                    "target_path": str(target_path),
                    "backup_path": str(backup_path) if had_original else "",
                    "had_original": had_original,
                }
            )
    except Exception:
        for item in reversed(applied_files):
            target_path = Path(item["target_path"])
            backup_path_text = clean_text(item.get("backup_path"))
            if item.get("had_original") and backup_path_text:
                backup_path = Path(backup_path_text)
                if backup_path.exists():
                    ensure_dir(target_path.parent)
                    shutil.copy2(backup_path, target_path)
            elif target_path.exists():
                target_path.unlink()
        if backup_root.exists():
            shutil.rmtree(backup_root)
        raise

    active_mods.append(
        {
            "player_id": player_id,
            "mod_identity": identity,
            "mod_title": mod_title,
            "backup_root": str(backup_root),
            "extracted_dir": clean_text(stored_mod.get("extracted_dir")),
            "files": applied_files,
        }
    )
    save_active_online_runtime_mods(active_mods)

    if replaced_titles:
        message = f"Replaced {', '.join(replaced_titles)} and loaded {mod_title} from {extracted_modded.parent}."
    elif len(active_mods) > 1:
        message = f"Loaded {mod_title} from {extracted_modded.parent} alongside {len(active_mods) - 1} other loaded mod(s)."
    else:
        message = f"Loaded {mod_title} from {extracted_modded.parent}."

    return {
        "action": "loaded",
        "modded_path": str(extracted_modded.parent),
        "message": message,
    }


def installed_mod_identities(player_id: str) -> set[str]:
    manifest = load_online_profile_manifest(player_id)
    profile_dir = online_profile_dir(player_id)
    installed = set()
    for mod in manifest.get("mods", []):
        if not isinstance(mod, dict):
            continue
        identity = mod_identity(mod)
        local_file = clean_text(mod.get("local_file"))
        if identity and local_file and (profile_dir / local_file).exists():
            installed.add(identity)
    return installed


def installed_mod_count(player_id: str) -> int:
    return len(installed_mod_identities(player_id))


def load_installed_online_mod(player_id: str, mod: dict) -> str:
    result = toggle_online_mod_load(player_id, mod)
    return clean_text(result.get("modded_path")) or clean_text(result.get("message"))


def delete_installed_online_mod(player_id: str, mod: dict) -> str:
    identity = mod_identity(mod)
    if not identity:
        raise FileNotFoundError("This mod does not have a valid identity.")

    profile_dir = online_profile_dir(player_id)
    manifest = load_online_profile_manifest(player_id)
    manifest_mods = [item.copy() for item in manifest.get("mods", []) if isinstance(item, dict)]

    target_mod = None
    for item in manifest_mods:
        if mod_identity(item) == identity:
            target_mod = item
            break

    if target_mod is None:
        raise FileNotFoundError("This mod is not installed locally yet.")

    local_file = clean_text(target_mod.get("local_file"))
    if not local_file:
        raise FileNotFoundError("This mod does not have a saved local zip.")

    extracted_dir = clean_text(target_mod.get("extracted_dir"))
    zip_path = profile_dir / local_file
    if not zip_path.exists():
        raise FileNotFoundError(f"Installed zip was not found: {zip_path}")

    zip_path.unlink()
    if extracted_dir:
        extracted_root = profile_dir / extracted_dir
        if extracted_root.exists() and extracted_root.is_dir():
            shutil.rmtree(extracted_root)

    remaining_mods = [item for item in manifest_mods if mod_identity(item) != identity]
    updated_manifest = {
        "player_id": clean_text(manifest.get("player_id")) or player_id,
        "mods": remaining_mods,
        "skipped": [item for item in manifest.get("skipped", []) if isinstance(item, dict)],
    }

    remaining_zip = any(path.is_file() and path.suffix.lower() == ".zip" for path in profile_dir.iterdir())
    if remaining_mods or updated_manifest["skipped"] or remaining_zip:
        save_online_profile_manifest(player_id, updated_manifest)
    else:
        delete_online_profile(player_id)

    return local_file


def unique_zip_name(mod: dict, used_names: set[str]) -> str:
    raw_name = (
        clean_text(mod.get("file_name"))
        or clean_text(mod.get("github_asset_name"))
        or Path(urllib_parse.urlparse(clean_text(mod.get("download_url"))).path).name
        or "mod.zip"
    )
    file_name = safe_file_name(raw_name)
    if not file_name.lower().endswith(".zip"):
        file_name = f"{Path(file_name).stem or 'mod'}.zip"

    prefix = safe_folder_name(clean_text(mod.get("id")) or clean_text(mod.get("github_tag")) or clean_text(mod.get("name")))
    candidate = f"{prefix}-{file_name}" if prefix else file_name
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    stem = Path(candidate).stem
    suffix = Path(candidate).suffix or ".zip"
    index = 2
    while True:
        numbered = f"{stem}-{index}{suffix}"
        if numbered not in used_names:
            used_names.add(numbered)
            return numbered
        index += 1


def download_binary(url: str, target: Path, progress_callback=None, max_redirects: int = 5):
    current_url = clean_text(url)
    if not current_url:
        raise ValueError("Missing download URL.")

    for _ in range(max_redirects + 1):
        parsed = urllib_parse.urlparse(current_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Download URL must start with http:// or https://")

        request_path = parsed.path or "/"
        if parsed.query:
            request_path += "?" + parsed.query

        conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(parsed.netloc, timeout=30)
        try:
            conn.request(
                "GET",
                request_path,
                headers={
                    "Accept": "application/octet-stream",
                    "User-Agent": "Xzen-Service",
                },
            )
            response = conn.getresponse()

            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                response.read()
                if not location:
                    raise RuntimeError(f"Download redirect missing Location header: HTTP {response.status}")
                current_url = urllib_parse.urljoin(current_url, location)
                continue

            if response.status >= 400:
                message = response.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"HTTP {response.status}: {message or response.reason}")

            total = int(response.getheader("Content-Length") or 0)
            downloaded = 0
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total:
                        progress_callback(downloaded, total)
            return
        finally:
            conn.close()

    raise RuntimeError("Too many redirects while downloading zip.")


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

        boost = 28
        self._momentum += direction * boost
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


class SmoothListWidget(QtWidgets.QListWidget):
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

        boost = 28
        self._momentum += direction * boost
        self._momentum = max(-self._max_momentum, min(self._max_momentum, self._momentum))

        current = bar.value()
        target = current + (direction * self._wheel_step) + self._momentum
        target = max(bar.minimum(), min(bar.maximum(), target))

        if self._scroll_anim.state() == QtCore.QAbstractAnimation.Running:
            self._scroll_anim.stop()

        self._scroll_anim.setDuration(320)
        self._scroll_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
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

    def __init__(self, preview_url: str = "", parent=None, frame_size: QtCore.QSize | None = None, borderless: bool = False):
        super().__init__(parent)
        self.preview_url = clean_text(preview_url)
        self._reply = None
        self._movie = None
        self._buffer = None
        self._pixmap_data = b""
        frame_size = frame_size or QtCore.QSize(132, 92)
        self._scaled_movie_size = QtCore.QSize(max(1, frame_size.width() - 12), max(1, frame_size.height() - 12))

        if RemotePreviewFrame._network_manager is None:
            RemotePreviewFrame._network_manager = QtNetwork.QNetworkAccessManager()

        self.setFixedSize(frame_size)
        self.setObjectName("modPreviewFrame")
        self.setStyleSheet(f"""
            QFrame#modPreviewFrame {{
                background-color: #0d0d0d;
                border: {"none" if borderless else f"1px solid {BORDER}"};
                border-radius: 10px;
            }}
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0 if borderless else 6, 0 if borderless else 6, 0 if borderless else 6, 0 if borderless else 6)
        layout.setSpacing(0)

        self.label = QtWidgets.QLabel("")
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setStyleSheet(f"""
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        layout.addWidget(self.label)

        if self.preview_url:
            self._load_preview()

    def _load_preview(self):
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(self.preview_url))
        request.setHeader(QtNetwork.QNetworkRequest.UserAgentHeader, "Xzen-Service")
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


class ModListItemWidget(QtWidgets.QFrame):
    def __init__(self, mod: dict, installed: bool, parent=None):
        super().__init__(parent)
        self.mod = mod
        self.installed = installed
        self.selected = False

        self.setObjectName("modListItem")
        self.setFixedSize(156, 190)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        preview_url = clean_text(mod.get("preview_url"))
        self.preview = RemotePreviewFrame(
            preview_url=preview_url,
            parent=self,
            frame_size=QtCore.QSize(140, 104),
            borderless=True,
        )
        layout.addWidget(self.preview, 0, QtCore.Qt.AlignHCenter)

        title = clean_text(mod.get("release_title")) or clean_text(mod.get("name")) or "Untitled"
        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.title_label.setFixedHeight(38)
        self.title_label.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 800; background: transparent; border: none;")
        layout.addWidget(self.title_label)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; background: transparent; border: none;")
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        self._refresh_status_text()
        self._apply_style()

    def _refresh_status_text(self):
        self.status_label.setText("Installed" if self.installed else "Not installed")

    def _apply_style(self):
        border_color = ACCENT if self.selected else BORDER
        background_color = "#111111" if self.selected else PANEL
        self.setStyleSheet(f"""
            QFrame#modListItem {{
                background-color: {background_color};
                border: 1px solid {border_color};
                border-radius: 10px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)

    def set_selected(self, selected: bool):
        self.selected = bool(selected)
        self._apply_style()

    def set_installed(self, installed: bool):
        self.installed = installed
        self._refresh_status_text()

class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class PlayerFoundDialog(QtWidgets.QDialog):
    def __init__(self, player_id="#0001", mod_count=12, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Player Found")
        self.setModal(True)
        self.setFixedSize(360, 220)

        self.player_id = player_id
        self.mod_count = mod_count

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_DARK};
                color: {TEXT};
            }}
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("Player Found")
        title.setStyleSheet(f"""
            color: {TEXT};
            font-size: 18px;
            font-weight: 700;
        """)
        layout.addWidget(title)

        info_card = QtWidgets.QFrame()
        info_card.setStyleSheet(f"""
            QFrame {{
                background-color: {PANEL};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
        """)
        info_layout = QtWidgets.QVBoxLayout(info_card)
        info_layout.setContentsMargins(14, 14, 14, 14)
        info_layout.setSpacing(8)

        player_label = QtWidgets.QLabel(f"Player ID: {player_id}")
        player_label.setStyleSheet(
            f"color: {TEXT}; font-size: 14px; font-weight: 600;"
        )

        mod_text = "Unknown" if mod_count is None else str(mod_count)
        mods_label = QtWidgets.QLabel(f"Mods: {mod_text}")
        mods_label.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 13px;"
        )

        info_layout.addWidget(player_label)
        info_layout.addWidget(mods_label)
        layout.addWidget(info_card)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)

        self.close_btn = QtWidgets.QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        self.close_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        self.add_btn = QtWidgets.QPushButton("Add Person")
        self.add_btn.clicked.connect(self.accept)
        self.add_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        self.close_btn.setStyleSheet(f"""
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
        """)

        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {TEXT};
                color: {BG_DARK};
                border: 1px solid {ACCENT};
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #ffffff;
            }}
            QPushButton:pressed {{
                background-color: #dcdcdc;
            }}
        """)

        btn_row.addWidget(self.close_btn)
        btn_row.addWidget(self.add_btn)
        layout.addLayout(btn_row)


class PlayerModsDialog(QtWidgets.QDialog):
    install_requested = QtCore.pyqtSignal(object)
    delete_requested = QtCore.pyqtSignal(object)
    delete_local_requested = QtCore.pyqtSignal(object)

    def __init__(
        self,
        player_id: str,
        sharer_name: str,
        mods: list[dict],
        installed_keys: set[str],
        allow_delete: bool = False,
        active_keys: set[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Select Mod")
        self.setModal(True)
        self.setWindowFlags((self.windowFlags() | QtCore.Qt.WindowCloseButtonHint) & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setFixedSize(920, 640)
        self.player_id = player_id
        self.sharer_name = clean_text(sharer_name) or player_id
        self.mods = mods
        self.installed_keys = installed_keys
        self.allow_delete = allow_delete
        self.active_keys = {clean_text(item) for item in (active_keys or set()) if clean_text(item)}
        self.action = None
        self._installing = False

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_DARK};
                color: {TEXT};
            }}
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QtWidgets.QLabel(f"Mods shared by {self.sharer_name}")
        title.setStyleSheet(f"color: {TEXT}; font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel("Choose which mod you want to install or load.")
        subtitle.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        layout.addWidget(subtitle)

        content_row = QtWidgets.QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(18)

        self.mods_list = SmoothListWidget()
        self.mods_list.setMinimumSize(520, 360)
        self.mods_list.setMaximumWidth(520)
        self.mods_list.setSpacing(10)
        self.mods_list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.mods_list.setViewMode(QtWidgets.QListView.IconMode)
        self.mods_list.setFlow(QtWidgets.QListView.LeftToRight)
        self.mods_list.setWrapping(True)
        self.mods_list.setResizeMode(QtWidgets.QListView.Adjust)
        self.mods_list.setMovement(QtWidgets.QListView.Static)
        self.mods_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.mods_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.mods_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {PANEL};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 10px;
                padding: 8px;
                font-size: 13px;
                outline: none;
            }}
            QListWidget::item {{
                border: none;
                padding: 0px;
                margin: 0px;
            }}
            QListWidget::item:selected {{
                background: transparent;
                border: none;
            }}
        """)
        for mod in mods:
            status = "Installed" if mod_identity(mod) in installed_keys else "Not installed"
            item = QtWidgets.QListWidgetItem("")
            item.setData(QtCore.Qt.UserRole, mod)
            item.setSizeHint(QtCore.QSize(156, 190))
            self.mods_list.addItem(item)
            widget = ModListItemWidget(mod=mod, installed=status == "Installed", parent=self.mods_list)
            self.mods_list.setItemWidget(item, widget)
        self.mods_list.currentItemChanged.connect(self.update_selection_state)
        content_row.addWidget(self.mods_list, 0)

        details_panel = QtWidgets.QVBoxLayout()
        details_panel.setContentsMargins(0, 0, 0, 0)
        details_panel.setSpacing(8)

        self.details_section_title = QtWidgets.QLabel("Mod Description")
        self.details_section_title.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: 700;")
        details_panel.addWidget(self.details_section_title)

        self.details_card = QtWidgets.QFrame()
        self.details_card.setStyleSheet(f"""
            QFrame {{
                background-color: transparent;
                border: none;
            }}
        """)
        details_layout = QtWidgets.QVBoxLayout(self.details_card)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(6)

        self.details_mod_title = QtWidgets.QLabel("")
        self.details_mod_title.setWordWrap(True)
        self.details_mod_title.setStyleSheet(f"color: {TEXT}; font-size: 15px; font-weight: 800;")
        details_layout.addWidget(self.details_mod_title)

        self.details_meta_label = QtWidgets.QLabel("")
        self.details_meta_label.setWordWrap(True)
        self.details_meta_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        details_layout.addWidget(self.details_meta_label)

        details_title = QtWidgets.QLabel("Description")
        details_title.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        details_layout.addWidget(details_title)

        self.details_scroll = SmoothScrollArea()
        self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.details_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.details_scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
        """)

        self.details_description = QtWidgets.QLabel("")
        self.details_description.setWordWrap(True)
        self.details_description.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.details_description.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.details_description.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                color: {TEXT_DIM};
                border: none;
                padding: 0;
                font-size: 12px;
            }}
        """)
        self.details_description_wrap = QtWidgets.QWidget()
        details_description_layout = QtWidgets.QVBoxLayout(self.details_description_wrap)
        details_description_layout.setContentsMargins(0, 0, 0, 0)
        details_description_layout.setSpacing(0)
        details_description_layout.addWidget(self.details_description)
        details_description_layout.addStretch(1)
        self.details_scroll.setWidget(self.details_description_wrap)
        self.details_scroll.setMinimumHeight(220)
        details_layout.addWidget(self.details_scroll, 1)
        details_panel.addWidget(self.details_card, 1)
        content_row.addLayout(details_panel, 1)
        layout.addLayout(content_row, 1)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 13px;")
        layout.addWidget(self.status_label)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {PANEL};
                border: 1px solid {BORDER};
                border-radius: 6px;
                color: {TEXT};
                text-align: center;
                min-height: 18px;
            }}
            QProgressBar::chunk {{
                background-color: {TEXT};
                border-radius: 5px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        layout.addStretch(1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)

        self.close_btn = QtWidgets.QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        self.close_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.close_btn.setStyleSheet(f"""
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
        """)

        self.install_btn = QtWidgets.QPushButton("Install")
        self.install_btn.clicked.connect(self.accept_install)
        self.install_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.install_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {TEXT};
                color: {BG_DARK};
                border: 1px solid {ACCENT};
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #ffffff;
            }}
            QPushButton:pressed {{
                background-color: #dcdcdc;
            }}
            QPushButton:disabled {{
                background-color: #666666;
                color: #222222;
                border-color: #666666;
            }}
        """)

        self.delete_btn = QtWidgets.QPushButton("Delete")
        self.delete_btn.clicked.connect(self.accept_delete)
        self.delete_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.delete_btn.setVisible(self.allow_delete)
        self.delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #ff6b6b;
                border: 1px solid #7a2f2f;
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #1a0d0d;
                color: #ff8c8c;
                border-color: #b34747;
            }}
            QPushButton:pressed {{
                background-color: #241111;
            }}
            QPushButton:disabled {{
                color: #555555;
                border-color: #444444;
            }}
        """)

        self.delete_local_btn = QtWidgets.QPushButton("Delete Local")
        self.delete_local_btn.clicked.connect(self.accept_delete_local)
        self.delete_local_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.delete_local_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #ff6b6b;
                border: 1px solid #7a2f2f;
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #1a0d0d;
                color: #ff8c8c;
                border-color: #b34747;
            }}
            QPushButton:pressed {{
                background-color: #241111;
            }}
            QPushButton:disabled {{
                color: #555555;
                border-color: #444444;
            }}
        """)

        self.load_btn = QtWidgets.QPushButton("Load")
        self.load_btn.clicked.connect(self.accept_load)
        self.load_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.load_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #bb86fc;
                border: 1px solid #5b3a82;
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #120d19;
                color: #d1a7ff;
                border-color: #8d5fd3;
            }}
            QPushButton:pressed {{
                background-color: #1a1323;
            }}
            QPushButton:disabled {{
                color: #555555;
                border-color: #444444;
            }}
        """)

        btn_row.addWidget(self.close_btn)
        if self.allow_delete:
            btn_row.addWidget(self.delete_btn)
        btn_row.addWidget(self.delete_local_btn)
        btn_row.addWidget(self.load_btn)
        btn_row.addWidget(self.install_btn)
        layout.addLayout(btn_row)

        if self.mods_list.count():
            self.mods_list.setCurrentRow(0)
        self.update_selection_state()

    def selected_mod(self) -> dict | None:
        item = self.mods_list.currentItem()
        return item.data(QtCore.Qt.UserRole) if item is not None else None

    def sync_mod_card_selection(self):
        current_row = self.mods_list.currentRow()
        for index in range(self.mods_list.count()):
            item = self.mods_list.item(index)
            widget = self.mods_list.itemWidget(item) if item is not None else None
            if isinstance(widget, ModListItemWidget):
                widget.set_selected(index == current_row)

    def update_mod_details(self, mod: dict | None):
        if not isinstance(mod, dict):
            self.details_mod_title.setText("No mod selected")
            self.details_meta_label.setText("No mod selected.")
            self.details_description.setText("Select a mod to see its description.")
            return

        title = clean_text(mod.get("release_title")) or clean_text(mod.get("name")) or "Untitled"
        shared_by = clean_text(self.sharer_name) or clean_text(mod.get("player_id")) or clean_text(self.player_id) or "Unknown"
        version = clean_text(mod.get("version")) or clean_text(mod.get("github_tag")) or "unknown"
        file_name = clean_text(mod.get("file_name")) or "unknown"
        description = strip_markdown_images(clean_text(mod.get("description"))) or "No description provided."

        self.details_mod_title.setText(title)
        self.details_meta_label.setText(
            f"Shared by: {shared_by}   Version: {version}   File: {file_name}"
        )
        self.details_description.setText(description)

    def update_selection_state(self):
        mod = self.selected_mod()
        self.sync_mod_card_selection()
        self.update_mod_details(mod)
        if not isinstance(mod, dict):
            self.status_label.setText("No mod selected.")
            self.install_btn.setEnabled(False)
            self.load_btn.setEnabled(False)
            self.load_btn.setText("Load")
            self.delete_local_btn.setEnabled(False)
            if self.allow_delete:
                self.delete_btn.setEnabled(False)
            return

        installed = mod_identity(mod) in self.installed_keys
        identity = mod_identity(mod)
        is_active = installed and identity in self.active_keys
        if self._installing:
            self.install_btn.setEnabled(False)
            self.load_btn.setEnabled(False)
            self.load_btn.setText("Load")
            self.delete_local_btn.setEnabled(False)
            if self.allow_delete:
                self.delete_btn.setEnabled(False)
            return
        if installed:
            if is_active:
                status_text = "This mod is currently loaded into the game. Press Disable to restore the previous files."
                self.load_btn.setText("Disable")
            else:
                status_text = "This mod is installed locally and can be loaded now."
                self.load_btn.setText("Load")
            if self.allow_delete:
                status_text += " As the owner, you can also delete it from shared releases."
            self.status_label.setText(status_text)
            self.install_btn.setEnabled(False)
            self.load_btn.setEnabled(True)
            self.delete_local_btn.setEnabled(True)
            if self.allow_delete:
                self.delete_btn.setEnabled(True)
        else:
            status_text = "This mod is available to install."
            if self.allow_delete:
                status_text += " As the owner, you can also delete it from shared releases."
            self.status_label.setText(status_text)
            self.install_btn.setEnabled(True)
            self.load_btn.setEnabled(False)
            self.load_btn.setText("Load")
            self.delete_local_btn.setEnabled(False)
            if self.allow_delete:
                self.delete_btn.setEnabled(True)

    def accept_install(self):
        mod = self.selected_mod()
        if not isinstance(mod, dict) or self._installing:
            return
        self.install_requested.emit(mod)

    def accept_load(self):
        self.action = "load"
        self.accept()

    def accept_delete(self):
        mod = self.selected_mod()
        if not isinstance(mod, dict) or self._installing:
            return
        self.delete_requested.emit(mod)

    def accept_delete_local(self):
        mod = self.selected_mod()
        if not isinstance(mod, dict) or self._installing:
            return
        self.delete_local_requested.emit(mod)

    def begin_install(self, mod_title: str):
        self._installing = True
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Downloading {mod_title}...")
        self.mods_list.setEnabled(False)
        self.install_btn.setEnabled(False)
        self.load_btn.setEnabled(False)
        self.delete_local_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        if self.allow_delete:
            self.delete_btn.setEnabled(False)

    def update_install_progress(self, value: int, message: str = ""):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(max(0, min(100, int(value))))
        if message:
            self.status_label.setText(message)

    def finish_install(self, mod: dict, success: bool, message: str):
        self._installing = False
        self.mods_list.setEnabled(True)
        self.close_btn.setEnabled(True)
        if success:
            identity = mod_identity(mod)
            if identity:
                self.installed_keys.add(identity)
            item = self.mods_list.currentItem()
            if item is not None:
                widget = self.mods_list.itemWidget(item)
                if isinstance(widget, ModListItemWidget):
                    widget.set_installed(True)
            self.progress_bar.setValue(100)
        else:
            self.progress_bar.setValue(0)
        self.status_label.setText(message)
        self.update_selection_state()

    def finish_local_delete(self, mod: dict, message: str):
        identity = mod_identity(mod)
        if identity and identity in self.installed_keys:
            self.installed_keys.remove(identity)
        if identity:
            self.active_keys.discard(identity)
        item = self.mods_list.currentItem()
        if item is not None:
            widget = self.mods_list.itemWidget(item)
            if isinstance(widget, ModListItemWidget):
                widget.set_installed(False)
        self.status_label.setText(message)
        self.update_selection_state()

    def finish_shared_delete(self, mod: dict, message: str):
        identity = mod_identity(mod)
        if identity and identity in self.installed_keys:
            self.installed_keys.remove(identity)
        if identity:
            self.active_keys.discard(identity)

        remove_row = -1
        for index in range(self.mods_list.count()):
            item = self.mods_list.item(index)
            item_mod = item.data(QtCore.Qt.UserRole) if item is not None else None
            if isinstance(item_mod, dict) and mod_identity(item_mod) == identity:
                remove_row = index
                break

        if remove_row >= 0:
            self.mods = [item for item in self.mods if mod_identity(item) != identity]
            removed_item = self.mods_list.takeItem(remove_row)
            del removed_item
            if self.mods_list.count():
                self.mods_list.setCurrentRow(min(remove_row, self.mods_list.count() - 1))

        self.status_label.setText(message)
        self.update_selection_state()

    def finish_load_toggle(self, mod: dict, action: str, message: str):
        identity = mod_identity(mod)
        if action == "disabled":
            if identity:
                self.active_keys.discard(identity)
        elif action == "loaded" and identity:
            self.active_keys.add(identity)
            self.installed_keys.add(identity)
        self.status_label.setText(message)
        self.update_selection_state()


class GitHubRateLimitDialog(QtWidgets.QDialog):
    def __init__(self, player_id: str, reset_at: int | None, parent=None):
        super().__init__(parent)
        self.player_id = player_id
        self.reset_at = int(reset_at or (time.time() + 60))
        self.setWindowTitle("GitHub Rate Limited")
        self.setModal(True)
        self.setWindowFlags((self.windowFlags() | QtCore.Qt.WindowCloseButtonHint) & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.resize(520, 190)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_DARK};
                color: {TEXT};
            }}
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("GitHub is rate limiting this IP right now.")
        title.setWordWrap(True)
        title.setStyleSheet(f"color: {TEXT}; font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        self.body_label = QtWidgets.QLabel("")
        self.body_label.setWordWrap(True)
        self.body_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 13px;")
        layout.addWidget(self.body_label)

        hint_label = QtWidgets.QLabel("Press Mods again after the timer reaches zero.")
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        layout.addWidget(hint_label)

        layout.addStretch(1)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh_countdown)
        self.refresh_countdown()
        self.timer.start()

    def refresh_countdown(self):
        remaining = max(0, int(self.reset_at - time.time()))
        if remaining > 0:
            self.body_label.setText(
                f"Mods for {self.player_id} should be available again in {format_wait_time(remaining)}."
            )
            return

        self.body_label.setText(
            f"GitHub's rate-limit window should be over for {self.player_id}. You can press Mods again now."
        )
        self.timer.stop()

    def done(self, result):
        if self.timer.isActive():
            self.timer.stop()
        super().done(result)


class OnlinePlaySetupDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_config = None
        self.current_config = load_waifly_config()
        self.setWindowTitle("Online Play")
        self.setModal(True)
        self.setMinimumSize(560, 700)
        self.resize(580, 720)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_DARK};
                color: {TEXT};
            }}
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QtWidgets.QLabel("Set Up Online Play")
        title.setStyleSheet(f"""
            color: {TEXT};
            font-size: 20px;
            font-weight: 800;
            background: transparent;
        """)
        layout.addWidget(title)

        message = QtWidgets.QLabel(
            "Both options can use Xzen-Network features like friends, mod browsing, installing, and sharing. The difference is how your identity is shown and restored."
        )
        message.setWordWrap(True)
        message.setStyleSheet(f"""
            color: {TEXT_DIM};
            font-size: 13px;
            background: transparent;
        """)
        message.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        layout.addWidget(message)

        info_title = QtWidgets.QLabel("What happens next")
        info_title.setStyleSheet(f"""
            color: {TEXT};
            font-size: 13px;
            font-weight: 700;
            background: transparent;
        """)
        info_body = QtWidgets.QLabel(
            "Account mode gives you a username, profile picture support, and the same user ID again after reinstalling or changing PCs. Device ID mode keeps the old hardware-based behavior: you still get online features, but your profile is only the raw player ID and does not support account name or profile picture controls."
        )
        info_body.setWordWrap(True)
        info_body.setStyleSheet(f"""
            color: {TEXT_DIM};
            font-size: 12px;
            background: transparent;
        """)
        info_body.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)

        layout.addWidget(info_title)
        layout.addWidget(info_body)

        compare_note = QtWidgets.QLabel(
            "Quick summary:\n"
            "Account = username + profile picture + reusable login.\n"
            "Device ID = same core features, but ID-only profile with no name/avatar options."
        )
        compare_note.setWordWrap(True)
        compare_note.setStyleSheet(f"""
            color: {TEXT_DIM};
            font-size: 12px;
            background: transparent;
            border: none;
            padding: 0px;
        """)
        compare_note.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        layout.addWidget(compare_note)

        form = QtWidgets.QFrame()
        form.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border: none;
            }}
            QLineEdit {{
                min-height: 38px;
                background: transparent;
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 0 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        form_layout = QtWidgets.QVBoxLayout(form)
        form_layout.setContentsMargins(14, 14, 14, 14)
        form_layout.setSpacing(12)
        form.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)

        username_label = QtWidgets.QLabel("Username")
        username_label.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700; margin-bottom: 2px;")
        self.username_input = QtWidgets.QLineEdit()
        self.username_input.setPlaceholderText("for example: dasu")
        self.username_input.setText(clean_text(self.current_config.get("account_username")))

        password_label = QtWidgets.QLabel("Password")
        password_label.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700; margin-bottom: 2px;")
        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password_input.setPlaceholderText("at least 6 characters")

        confirm_label = QtWidgets.QLabel("Confirm Password")
        confirm_label.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700; margin-bottom: 2px;")
        self.confirm_input = QtWidgets.QLineEdit()
        self.confirm_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.confirm_input.setPlaceholderText("re-enter for account creation")

        hint = QtWidgets.QLabel(
            "Username rules: 3-24 chars using letters, numbers, `.`, `-`, or `_`."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; border: none;")
        hint.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)

        form_layout.addWidget(username_label)
        form_layout.addWidget(self.username_input)
        form_layout.addWidget(password_label)
        form_layout.addWidget(self.password_input)
        form_layout.addWidget(confirm_label)
        form_layout.addWidget(self.confirm_input)
        form_layout.addWidget(hint)
        layout.addWidget(form)

        action_row = QtWidgets.QGridLayout()
        action_row.setHorizontalSpacing(10)
        action_row.setVerticalSpacing(10)

        self.create_button = QtWidgets.QPushButton("Create Account")
        self.create_button.clicked.connect(self.create_account)
        self.create_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.create_button.setStyleSheet("""
            QPushButton {
                min-height: 38px;
                background-color: #ffffff;
                color: #050505;
                border: 1px solid #ffffff;
                border-radius: 8px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
            QPushButton:pressed {
                background-color: #dedede;
            }
        """)
        self.create_button.setMinimumHeight(42)

        self.login_button = QtWidgets.QPushButton("Log In")
        self.login_button.clicked.connect(self.login_account)
        self.login_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.login_button.setStyleSheet(f"""
            QPushButton {{
                min-height: 38px;
                background: transparent;
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                border-color: {ACCENT};
            }}
        """)
        self.login_button.setMinimumHeight(42)

        action_row.addWidget(self.create_button, 0, 0)
        action_row.addWidget(self.login_button, 0, 1)
        action_row.setColumnStretch(0, 1)
        action_row.setColumnStretch(1, 1)
        layout.addLayout(action_row)

        button_row = QtWidgets.QGridLayout()
        button_row.setHorizontalSpacing(10)
        button_row.setVerticalSpacing(10)

        self.later_button = QtWidgets.QPushButton("Later")
        self.later_button.clicked.connect(self.reject)
        self.later_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.later_button.setStyleSheet(f"""
            QPushButton {{
                min-height: 42px;
                background: transparent;
                color: {TEXT_DIM};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                color: {TEXT};
                border-color: {ACCENT};
            }}
        """)
        self.later_button.setMinimumHeight(42)

        self.device_button = QtWidgets.QPushButton("Use Device ID")
        self.device_button.clicked.connect(self.use_device_identity)
        self.device_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.device_button.setStyleSheet("""
            QPushButton {
                min-height: 38px;
                min-width: 128px;
                background-color: transparent;
                color: #eeeeee;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                border-color: #ffffff;
            }
        """)
        self.device_button.setMinimumHeight(42)

        button_row.addWidget(self.device_button, 0, 0)
        button_row.addWidget(self.later_button, 0, 1)
        button_row.setColumnStretch(0, 1)
        button_row.setColumnStretch(1, 1)
        layout.addLayout(button_row)
        layout.addStretch(1)

    def create_account(self):
        try:
            validate_account_credentials(
                self.username_input.text(),
                self.password_input.text(),
                require_confirm=self.confirm_input.text(),
            )
            self.result_config = configure_account_identity(
                self.current_config,
                self.username_input.text(),
                self.password_input.text(),
                mode="create",
            )
        except Exception as e:
            show_compact_warning(self, "Create Account", str(e))
            return

        self.accept()

    def login_account(self):
        try:
            self.result_config = configure_account_identity(
                self.current_config,
                self.username_input.text(),
                self.password_input.text(),
                mode="login",
            )
        except Exception as e:
            show_compact_warning(self, "Log In", str(e))
            return

        self.accept()

    def use_device_identity(self):
        config = dict(self.current_config)
        config.update({
            "online_play_enabled": True,
            "identity_mode": "device",
            "account_username": "",
            "account_password_hash": "",
            "user_id": "",
        })
        self.result_config = save_waifly_config(config)
        self.accept()


class PlayerCard(QtWidgets.QFrame):
    removed = QtCore.pyqtSignal(str)
    changed = QtCore.pyqtSignal(str, str, object)
    install_clicked = QtCore.pyqtSignal(str)

    def __init__(
        self,
        player_id: str,
        mod_count: int,
        display_name: str = None,
        image_path: str = None,
        installed: bool = False,
        is_owner: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.player_id = player_id
        self.mod_count = mod_count
        self.display_name = display_name or player_id
        self.image_path = image_path
        self.installed = installed
        self.is_owner = is_owner
        self.movie = None

        self.setFixedSize(180, 206)
        self.setObjectName("playerCard")
        self.setStyleSheet(f"""
            QFrame#playerCard {{
                background-color: {PANEL};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
            QFrame#playerCard:hover {{
                border: 1px solid {ACCENT};
                background-color: #101010;
            }}
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        top_row = QtWidgets.QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)

        self.name_label = ClickableLabel(self.display_name)
        self.name_label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.name_label.setStyleSheet(f"""
            color: {TEXT};
            font-size: 11px;
            font-weight: 700;
            padding: 2px 0px;
            background: transparent;
            border: none;
        """)
        self.name_label.clicked.connect(self.copy_id_to_clipboard)
        top_row.addWidget(self.name_label, 1, QtCore.Qt.AlignLeft)

        self.owner_badge = QtWidgets.QLabel("Owner")
        self.owner_badge.setVisible(self.is_owner)
        self.owner_badge.setAlignment(QtCore.Qt.AlignCenter)
        self.owner_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {TEXT};
                color: {BG_DARK};
                border-radius: 8px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 800;
            }}
        """)
        top_row.addWidget(self.owner_badge, 0, QtCore.Qt.AlignVCenter)

        self.menu_btn = QtWidgets.QToolButton()
        self.menu_btn.setText("⋮")
        self.menu_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.menu_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.menu_btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                color: {TEXT_DIM};
                border: none;
                font-size: 16px;
                font-weight: 700;
                padding: 0px 4px;
            }}
            QToolButton:hover {{
                color: {TEXT};
            }}
        """)

        self.menu = QtWidgets.QMenu(self)
        self.menu.setStyleSheet(f"""
            QMenu {{
                background-color: {PANEL};
                color: {TEXT};
                border: 1px solid {BORDER};
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 18px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: #161616;
            }}
        """)

        self.action_edit_name = self.menu.addAction("Edit Name")
        self.action_add_image = self.menu.addAction("Add / Change Image")
        self.menu.addSeparator()
        self.action_unfriend = self.menu.addAction("Unfriend")

        self.action_edit_name.triggered.connect(self.edit_name)
        self.action_add_image.triggered.connect(self.change_image)
        self.action_unfriend.triggered.connect(self.unfriend)

        self.menu_btn.setMenu(self.menu)
        top_row.addWidget(self.menu_btn, 0, QtCore.Qt.AlignRight)
        layout.addLayout(top_row)

        self.image_container = QtWidgets.QFrame()
        self.image_container.setObjectName("imageContainer")
        self.image_container.setFixedHeight(128)
        self.image_container.setStyleSheet(f"""
            QFrame#imageContainer {{
                background-color: #0d0d0d;
                border: none;
                border-radius: 10px;
            }}
        """)

        image_layout = QtWidgets.QVBoxLayout(self.image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(0)

        self.image_label = QtWidgets.QLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(1, 1)
        self.image_label.setScaledContents(False)
        self.image_label.setStyleSheet("border: none; background: transparent;")
        image_layout.addWidget(self.image_label)

        layout.addWidget(self.image_container)

        bottom_row = QtWidgets.QHBoxLayout()
        bottom_row.setContentsMargins(0, 2, 0, 0)
        bottom_row.setSpacing(6)

        self.load_btn = QtWidgets.QPushButton("View Mods")
        self.load_btn.setFixedHeight(24)
        self.load_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        if self.installed:
            self.load_btn.setToolTip("Some mods are already installed")
        else:
            self.load_btn.setToolTip("Choose a mod to install")
        self.load_btn.clicked.connect(lambda: self.install_clicked.emit(self.player_id))
        self.load_btn.setStyleSheet(f"""
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
            QPushButton:pressed {{
                background-color: #dcdcdc;
            }}
        """)

        self.mods_label = QtWidgets.QLabel(format_mod_count_label(self.mod_count))
        self.mods_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.mods_label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {TEXT_DIM};
                font-size: 11px;
                font-weight: 500;
                padding: 0;
                margin: 0;
            }}
        """)

        bottom_row.addWidget(self.load_btn, 0)
        bottom_row.addStretch(1)
        bottom_row.addWidget(self.mods_label, 0)

        layout.addLayout(bottom_row)

        self.refresh_visual()

    def _image_target_size(self):
        container_size = self.image_container.size()
        w = max(1, container_size.width())
        h = max(1, container_size.height())

        if w <= 1 or h <= 1:
            return QtCore.QSize(160, 128)

        return QtCore.QSize(w, h)

    def refresh_visual(self):
        self.name_label.setText(self.display_name)
        self.mods_label.setText(format_mod_count_label(self.mod_count))
        self.owner_badge.setVisible(self.is_owner)

        self.image_label.clear()
        self.image_label.setText("")
        self.image_label.setPixmap(QtGui.QPixmap())
        self.image_label.setStyleSheet(f"""
            border: none;
            background: transparent;
            color: {TEXT};
            font-size: 22px;
            font-weight: 800;
        """)

        if self.movie:
            self.movie.stop()
            self.movie = None

        target_size = self._image_target_size()

        if self.image_path:
            lower = str(self.image_path).lower()

            if lower.endswith(".gif"):
                self.movie = QtGui.QMovie(self.image_path)
                if self.movie.isValid():
                    self.movie.setScaledSize(target_size)
                    self.image_label.setMovie(self.movie)
                    self.image_label.setAlignment(QtCore.Qt.AlignCenter)
                    self.movie.start()
                    return

            pix = QtGui.QPixmap(self.image_path)
            if not pix.isNull():
                scaled = pix.scaled(
                    target_size,
                    QtCore.Qt.KeepAspectRatioByExpanding,
                    QtCore.Qt.SmoothTransformation
                )

                x = max(0, (scaled.width() - target_size.width()) // 2)
                y = max(0, (scaled.height() - target_size.height()) // 2)

                cropped = scaled.copy(x, y, target_size.width(), target_size.height())
                self.image_label.setPixmap(cropped)
                self.image_label.setAlignment(QtCore.Qt.AlignCenter)
                return

        self.image_label.setText(self.player_id)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self.refresh_visual)

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self.refresh_visual)

    def copy_id_to_clipboard(self):
        copy_player_id_to_clipboard(self.player_id, self)

    def edit_name(self):
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Edit Display Name",
            "Display name:",
            text=self.display_name
        )
        if ok and new_name.strip():
            self.display_name = new_name.strip()
            self.refresh_visual()
            self.changed.emit(self.player_id, self.display_name, self.image_path)

    def change_image(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Choose Profile Image",
            "",
            "Images (*.png *.jpg *.jpeg *.gif)"
        )
        if file_path:
            self.image_path = file_path
            self.refresh_visual()
            self.changed.emit(self.player_id, self.display_name, self.image_path)

    def unfriend(self):
        self.removed.emit(self.player_id)


class PlayerIdRequestWorker(QtCore.QThread):
    succeeded = QtCore.pyqtSignal(str, dict)
    failed = QtCore.pyqtSignal(str, str)

    def __init__(self, action: str, base_url: str, lookup_value: str, parent=None):
        super().__init__(parent)
        self.action = action
        self.base_url = base_url
        self.lookup_value = lookup_value

    def run(self):
        try:
            if self.action == "exists":
                result = resolve_friend_search(self.base_url, self.lookup_value)
            elif self.action == "register":
                result = register_player_id(self.base_url, self.lookup_value)
            else:
                raise ValueError(f"Unknown action: {self.action}")
            self.succeeded.emit(self.action, result)
        except Exception as e:
            self.failed.emit(self.action, str(e) or e.__class__.__name__)


class PlayerModsListWorker(QtCore.QThread):
    succeeded = QtCore.pyqtSignal(str, object)
    failed = QtCore.pyqtSignal(str, object)

    def __init__(self, base_url: str, player_id: str, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.player_id = player_id

    def run(self):
        try:
            mods = [
                mod for mod in fetch_player_mods(self.base_url, self.player_id)
                if clean_text(mod.get("download_url"))
            ]
            self.succeeded.emit(self.player_id, mods)
        except GitHubRateLimitError as e:
            self.failed.emit(
                self.player_id,
                {
                    "type": "github_rate_limit",
                    "message": str(e),
                    "reset_at": e.reset_at,
                    "secondary": e.secondary,
                },
            )
        except Exception as e:
            self.failed.emit(self.player_id, str(e) or e.__class__.__name__)


class PlayerModsDownloadWorker(QtCore.QThread):
    status = QtCore.pyqtSignal(str)
    progress = QtCore.pyqtSignal(int, str)
    succeeded = QtCore.pyqtSignal(str, int, str)
    failed = QtCore.pyqtSignal(str, str)

    def __init__(self, base_url: str, player_id: str, mods: list[dict] | None = None, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.player_id = player_id
        self.mods = [mod.copy() for mod in mods] if mods else None

    def run(self):
        try:
            mods = self.mods or [
                mod for mod in fetch_player_mods(self.base_url, self.player_id)
                if clean_text(mod.get("download_url"))
            ]
            if not mods:
                raise RuntimeError(f"No shared mod files were found for {self.player_id}.")

            profile_name = safe_folder_name(self.player_id)
            final_dir = online_profile_dir(self.player_id)
            temp_dir = ONLINE_PROFILES_DIR / f".{profile_name}.tmp"

            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            if final_dir.exists():
                shutil.copytree(final_dir, temp_dir)
            else:
                temp_dir.mkdir(parents=True, exist_ok=True)

            existing_manifest = load_online_profile_manifest(self.player_id)
            existing_mods = [mod.copy() for mod in existing_manifest.get("mods", []) if isinstance(mod, dict)]
            existing_skipped = [item.copy() for item in existing_manifest.get("skipped", []) if isinstance(item, dict)]
            existing_mods_by_key = {
                mod_identity(mod): mod.copy()
                for mod in existing_mods
                if mod_identity(mod)
            }
            used_names = {
                path.name
                for path in temp_dir.iterdir()
                if path.is_file() and path.suffix.lower() == ".zip"
            }
            downloaded_mods = []
            skipped = list(existing_skipped)
            try:
                for index, mod in enumerate(mods, 1):
                    identity = mod_identity(mod)
                    file_name = unique_zip_name(mod, used_names)
                    target = temp_dir / file_name
                    title = clean_text(mod.get("name")) or clean_text(mod.get("id")) or file_name
                    self.status.emit(f"Downloading release {index}/{len(mods)}: {title}")

                    def on_progress(downloaded: int, total: int, mod_title: str = title):
                        percent = int((downloaded / max(total, 1)) * 100)
                        self.progress.emit(percent, f"Downloading {mod_title}... {percent}%")

                    try:
                        download_binary(clean_text(mod.get("download_url")), target, progress_callback=on_progress)
                    except Exception as e:
                        skipped.append({
                            "name": title,
                            "download_url": clean_text(mod.get("download_url")),
                            "error": str(e) or e.__class__.__name__,
                        })
                        if target.exists():
                            target.unlink()
                        self.status.emit(f"Skipped {title}: {str(e) or e.__class__.__name__}")
                        continue

                    mod = mod.copy()
                    mod["local_file"] = file_name
                    downloaded_mods.append(mod)
                    if identity:
                        existing_mods_by_key[identity] = mod.copy()

                if not downloaded_mods:
                    first_error = skipped[0]["error"] if skipped else "No zip assets were downloaded."
                    raise RuntimeError(f"No shared mod zips could be downloaded for {self.player_id}. {first_error}")

                manifest = {
                    "player_id": self.player_id,
                    "mods": list(existing_mods_by_key.values()),
                    "skipped": skipped,
                }
                (temp_dir / "manifest.json").write_text(
                    json.dumps(manifest, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

                if final_dir.exists():
                    shutil.rmtree(final_dir)
                temp_dir.replace(final_dir)
            except Exception:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                raise

            self.succeeded.emit(self.player_id, len(downloaded_mods), str(final_dir))
        except Exception as e:
            self.failed.emit(self.player_id, str(e) or e.__class__.__name__)


class ServicePage(QtWidgets.QWidget):
    GRID_COLUMNS = 4

    def __init__(self):
        super().__init__()
        self.players = load_friends()
        self.waifly_config = load_waifly_config()
        self.account_avatar_movie = None
        self._user_id_prompt_active = False
        self.search_worker = None
        self.register_worker = None
        self.mods_list_worker = None
        self.download_worker = None
        self.active_mods_dialog = None
        self.active_download_dialog = None
        self.active_download_mod = None
        self.github_rate_limit_reset_at = None
        self.github_rate_limit_player_id = ""
        self.github_rate_limit_timer = QtCore.QTimer(self)
        self.github_rate_limit_timer.setInterval(1000)
        self.github_rate_limit_timer.timeout.connect(self.update_github_rate_limit_status)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {BG_DARK};
                color: {TEXT};
            }}
        """)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        header_row = QtWidgets.QHBoxLayout()
        header_row.setSpacing(12)

        header_text = QtWidgets.QVBoxLayout()
        header_text.setContentsMargins(0, 0, 0, 0)
        header_text.setSpacing(4)

        title = QtWidgets.QLabel("Friendlist")
        title.setStyleSheet(f"""
            color: {TEXT};
            font-size: 22px;
            font-weight: 700;
            background: transparent;
        """)
        header_text.addWidget(title)

        subtitle = QtWidgets.QLabel("Search usernames or player IDs and service tools.")
        subtitle.setStyleSheet(f"""
            color: {TEXT_DIM};
            font-size: 13px;
            background: transparent;
        """)
        header_text.addWidget(subtitle)
        header_row.addLayout(header_text, 1)

        self.account_avatar_label = QtWidgets.QLabel()
        self.account_avatar_label.setFixedSize(34, 34)
        self.account_avatar_label.setAlignment(QtCore.Qt.AlignCenter)
        self.account_avatar_label.setStyleSheet("background: transparent; border: none;")
        self.account_avatar_label.hide()

        self.account_login_button = QtWidgets.QPushButton("Log In")
        self.account_login_button.setMinimumHeight(38)
        self.account_login_button.clicked.connect(self.handle_account_login)
        self.account_login_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.account_login_button.setStyleSheet(f"""
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
        """)

        self.account_menu = QtWidgets.QMenu(self)
        self.account_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {PANEL};
                color: {TEXT};
                border: 1px solid {BORDER};
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: #161616;
            }}
        """)
        self.action_change_account_avatar = self.account_menu.addAction("Set Profile Picture")
        self.action_remove_account_avatar = self.account_menu.addAction("Remove Profile Picture")
        self.account_menu.addSeparator()
        self.action_logout_account = self.account_menu.addAction("Log Out")
        self.action_change_account_avatar.triggered.connect(self.change_account_avatar)
        self.action_remove_account_avatar.triggered.connect(self.remove_account_avatar)
        self.action_logout_account.triggered.connect(self.logout_account)

        self.account_menu_button = QtWidgets.QToolButton()
        self.account_menu_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.account_menu_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.account_menu_button.setMenu(self.account_menu)
        self.account_menu_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.account_menu_button.setMinimumHeight(38)
        self.account_menu_button.setStyleSheet(f"""
            QToolButton {{
                background-color: {PANEL};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 0 14px;
                font-size: 12px;
                font-weight: 700;
            }}
            QToolButton:hover {{
                border-color: {ACCENT};
            }}
            QToolButton::menu-indicator {{
                image: none;
                width: 0px;
            }}
        """)
        self.account_menu_button.hide()

        account_box = QtWidgets.QHBoxLayout()
        account_box.setContentsMargins(0, 0, 0, 0)
        account_box.setSpacing(8)
        account_box.addWidget(self.account_avatar_label, 0, QtCore.Qt.AlignVCenter)
        account_box.addWidget(self.account_menu_button, 0, QtCore.Qt.AlignVCenter)
        account_box.addWidget(self.account_login_button, 0, QtCore.Qt.AlignVCenter)
        header_row.addLayout(account_box, 0)
        root.addLayout(header_row)

        local_id_label = QtWidgets.QLabel("Local User ID")
        local_id_label.setStyleSheet(f"""
            color: {TEXT_DIM};
            font-size: 12px;
            font-weight: 700;
            background: transparent;
        """)
        root.addWidget(local_id_label)

        local_id_row = QtWidgets.QHBoxLayout()
        local_id_row.setSpacing(10)

        self.local_user_id_input = QtWidgets.QLineEdit()
        self.local_user_id_input.setReadOnly(True)
        self.local_user_id_input.setMinimumHeight(42)
        self.local_user_id_input.setPlaceholderText("No local user ID")
        self.local_user_id_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {PANEL};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 0 14px;
                font-size: 13px;
                font-weight: 700;
            }}
            QLineEdit:focus {{
                border: 1px solid {ACCENT};
            }}
        """)

        self.copy_local_user_id_button = QtWidgets.QPushButton("Copy")
        self.copy_local_user_id_button.setMinimumHeight(42)
        self.copy_local_user_id_button.clicked.connect(self.copy_local_user_id)
        self.copy_local_user_id_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.copy_local_user_id_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {PANEL};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                border: 1px solid {ACCENT};
            }}
            QPushButton:pressed {{
                background-color: #141414;
            }}
        """)

        local_id_row.addWidget(self.local_user_id_input, 1)
        local_id_row.addWidget(self.copy_local_user_id_button, 0)
        root.addLayout(local_id_row)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(10)

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Search username or player ID...")
        self.search_input.setMinimumHeight(42)
        self.search_input.returnPressed.connect(self.handle_search)
        self.search_input.setStyleSheet(f"""
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
        """)

        self.search_button = QtWidgets.QPushButton("Search")
        self.search_button.setMinimumHeight(42)
        self.search_button.clicked.connect(self.handle_search)
        self.search_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.search_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {TEXT};
                color: {BG_DARK};
                border: 1px solid {ACCENT};
                border-radius: 6px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #ffffff;
            }}
            QPushButton:pressed {{
                background-color: #dcdcdc;
            }}
        """)

        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.search_button, 0)
        root.addLayout(search_row)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet(f"""
            color: {TEXT_DIM};
            font-size: 12px;
            background: transparent;
        """)
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        root.addSpacing(8)

        self.gallery_scroll = SmoothScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.gallery_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.gallery_scroll.setStyleSheet(f"""
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
        """)

        self.gallery_wrap = QtWidgets.QWidget()
        self.gallery_wrap.setAutoFillBackground(True)
        self.gallery_wrap.setStyleSheet(f"""
            QWidget {{
                background-color: {BG_DARK};
            }}
        """)

        self.gallery_layout = QtWidgets.QGridLayout(self.gallery_wrap)
        self.gallery_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery_layout.setHorizontalSpacing(14)
        self.gallery_layout.setVerticalSpacing(14)
        self.gallery_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)

        self.gallery_scroll.setWidget(self.gallery_wrap)
        root.addWidget(self.gallery_scroll, 1)

        self.refresh_local_user_id()
        self.refresh_account_controls()
        self.refresh_gallery()
        if self.waifly_config.get("user_id_was_reset"):
            self.set_status(f"Local player ID was restored to this device ID: {self.waifly_config['user_id']}.")
        elif self.waifly_config.get("identity_mode") == "account" and self.waifly_config.get("account_username"):
            self.set_status(
                f"Signed in as {display_account_name(self.waifly_config['account_username'])} with player ID {self.waifly_config['user_id']}."
            )
        if not waifly_config_needs_user_id(self.waifly_config) and self.waifly_config.get("identity_mode") != "account":
            QtCore.QTimer.singleShot(0, self.register_local_player_id)

    def clear_github_rate_limit_status(self):
        if self.github_rate_limit_timer.isActive():
            self.github_rate_limit_timer.stop()
        self.github_rate_limit_reset_at = None
        self.github_rate_limit_player_id = ""

    def start_github_rate_limit_status(self, player_id: str, reset_at: int | None):
        self.github_rate_limit_player_id = player_id
        self.github_rate_limit_reset_at = int(reset_at or (time.time() + 60))
        self.update_github_rate_limit_status()
        if self.github_rate_limit_reset_at > int(time.time()):
            self.github_rate_limit_timer.start()

    def update_github_rate_limit_status(self):
        if self.github_rate_limit_reset_at is None:
            return

        remaining = max(0, int(self.github_rate_limit_reset_at - time.time()))
        player_id = self.github_rate_limit_player_id or "this friend"
        if remaining > 0:
            self.set_status(
                f"GitHub is rate limiting this IP. Mods for {player_id} should be available again in {format_wait_time(remaining)}."
            )
            return

        self.clear_github_rate_limit_status()
        self.set_status(f"GitHub's rate limit should be over for {player_id}. Press Mods again.")

    def handle_search(self):
        if self.search_worker is not None:
            return

        query = clean_text(self.search_input.text())
        player_id = normalize_player_id(query)
        username = normalize_account_username(query)
        normalized_query = player_id or username
        if not normalized_query:
            self.set_status("Enter a valid username or player ID.")
            show_compact_warning(
                self,
                "Invalid Search",
                "Use a Waifly username or a player ID like #A1B2C3D4. Older 4-digit IDs are still supported.",
            )
            return

        self.search_input.setText(normalized_query)
        self.set_status(f"Checking {normalized_query} on Xzen-Network...")
        self.search_button.setEnabled(False)
        self.search_input.setEnabled(False)

        self.search_worker = PlayerIdRequestWorker(
            action="exists",
            base_url=self.waifly_config["api_base_url"],
            lookup_value=normalized_query,
            parent=self,
        )
        self.search_worker.succeeded.connect(self.on_worker_finished)
        self.search_worker.failed.connect(self.on_worker_failed)
        self.search_worker.start()

    def register_local_player_id(self):
        if self.register_worker is not None:
            return

        player_id = normalize_player_id(self.waifly_config.get("user_id"))
        if not player_id:
            self.set_status("Xzen-Network user ID is not configured yet.")
            return

        self.set_status(f"Registering local player ID {player_id} with Xzen-Network...")
        self.register_worker = PlayerIdRequestWorker(
            action="register",
            base_url=self.waifly_config["api_base_url"],
            lookup_value=player_id,
            parent=self,
        )
        self.register_worker.succeeded.connect(self.on_worker_finished)
        self.register_worker.failed.connect(self.on_worker_failed)
        self.register_worker.start()

    def refresh_local_user_id(self):
        player_id = normalize_player_id(self.waifly_config.get("user_id"))
        self.local_user_id_input.setText(player_id)
        self.local_user_id_input.setCursorPosition(0)
        self.copy_local_user_id_button.setEnabled(bool(player_id))

    def _account_avatar_pixmap(self, image_path: str, username: str, size: int = 34) -> QtGui.QPixmap:
        diameter = max(24, int(size))
        pixmap = QtGui.QPixmap(diameter, diameter)
        pixmap.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        clip = QtGui.QPainterPath()
        clip.addEllipse(0, 0, diameter, diameter)
        painter.setClipPath(clip)

        source = QtGui.QPixmap(clean_text(image_path))
        if not source.isNull():
            scaled = source.scaled(
                diameter,
                diameter,
                QtCore.Qt.KeepAspectRatioByExpanding,
                QtCore.Qt.SmoothTransformation,
            )
            x = max(0, (scaled.width() - diameter) // 2)
            y = max(0, (scaled.height() - diameter) // 2)
            painter.drawPixmap(0, 0, scaled.copy(x, y, diameter, diameter))
        else:
            painter.fillPath(clip, QtGui.QColor("#151515"))
            pen = QtGui.QPen(QtGui.QColor(BORDER))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawEllipse(0, 0, diameter - 1, diameter - 1)
            painter.setPen(QtGui.QColor(TEXT))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(11)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, (clean_text(username)[:1] or "?").upper())

        painter.end()
        return pixmap

    def _account_avatar_from_source(self, source: QtGui.QPixmap, username: str, size: int = 34) -> QtGui.QPixmap:
        diameter = max(24, int(size))
        pixmap = QtGui.QPixmap(diameter, diameter)
        pixmap.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        clip = QtGui.QPainterPath()
        clip.addEllipse(0, 0, diameter, diameter)
        painter.setClipPath(clip)

        if not source.isNull():
            scaled = source.scaled(
                diameter,
                diameter,
                QtCore.Qt.KeepAspectRatioByExpanding,
                QtCore.Qt.SmoothTransformation,
            )
            x = max(0, (scaled.width() - diameter) // 2)
            y = max(0, (scaled.height() - diameter) // 2)
            painter.drawPixmap(0, 0, scaled.copy(x, y, diameter, diameter))
        else:
            painter.fillPath(clip, QtGui.QColor("#151515"))
            pen = QtGui.QPen(QtGui.QColor(BORDER))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawEllipse(0, 0, diameter - 1, diameter - 1)
            painter.setPen(QtGui.QColor(TEXT))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(11)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, (clean_text(username)[:1] or "?").upper())

        painter.end()
        return pixmap

    def _update_account_avatar_movie_frame(self, username: str):
        if self.account_avatar_movie is None:
            return
        frame = self.account_avatar_movie.currentPixmap()
        self.account_avatar_label.setPixmap(self._account_avatar_from_source(frame, username))

    def refresh_account_controls(self):
        username = clean_text(self.waifly_config.get("account_username"))
        display_name = display_account_name(username)
        identity_mode = normalize_identity_mode(self.waifly_config.get("identity_mode"))
        has_user_id = bool(normalize_player_id(self.waifly_config.get("user_id")))
        logged_in = (
            identity_mode == "account"
            and bool(username)
            and has_user_id
        )

        if not logged_in:
            self.account_login_button.setText("Switch to Account" if identity_mode == "device" and has_user_id else "Log In")
        self.account_login_button.setVisible(not logged_in)
        self.account_avatar_label.setVisible(logged_in)
        self.account_menu_button.setVisible(logged_in)

        if self.account_avatar_movie is not None:
            self.account_avatar_movie.stop()
            self.account_avatar_label.setMovie(None)
            self.account_avatar_movie = None

        if not logged_in:
            self.account_avatar_label.clear()
            return

        avatar_path = clean_text(self.waifly_config.get("account_avatar_path"))
        if avatar_path.lower().endswith(".gif"):
            movie = QtGui.QMovie(avatar_path)
            if movie.isValid():
                movie.setScaledSize(QtCore.QSize(34, 34))
                self.account_avatar_movie = movie
                movie.frameChanged.connect(lambda _frame, name=username: self._update_account_avatar_movie_frame(name))
                self._update_account_avatar_movie_frame(username)
                movie.start()
            else:
                self.account_avatar_label.setPixmap(self._account_avatar_pixmap(avatar_path, username))
        else:
            self.account_avatar_label.setPixmap(self._account_avatar_pixmap(avatar_path, username))
        self.account_menu_button.setText(f"{display_name} v")
        self.action_remove_account_avatar.setEnabled(bool(avatar_path))

    def refresh_waifly_config(self):
        self.waifly_config = load_waifly_config()
        self.players = load_friends()
        self.refresh_local_user_id()
        self.refresh_account_controls()
        self.refresh_gallery()

    def handle_account_login(self):
        prompted_config = prompt_for_online_play_user_id(parent=self)
        if not isinstance(prompted_config, dict):
            self.set_status("Account setup was cancelled.")
            return

        self.waifly_config = prompted_config
        self.refresh_waifly_config()

        if self.waifly_config.get("identity_mode") == "account" and self.waifly_config.get("account_username"):
            self.set_status(
                f"Account {display_account_name(self.waifly_config['account_username'])} is ready with player ID {self.waifly_config['user_id']}."
            )
            return

        self.set_status(f"Local player ID {self.waifly_config['user_id']} is ready for online play.")
        self.register_local_player_id()

    def change_account_avatar(self):
        if self.waifly_config.get("identity_mode") != "account" or not clean_text(self.waifly_config.get("account_username")):
            self.set_status("Log in to an account before setting a profile picture.")
            return

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Choose Profile Picture",
            "",
            "Images (*.png *.jpg *.jpeg *.gif)",
        )
        if not file_path:
            return

        self.waifly_config = update_account_avatar(self.waifly_config, file_path)
        self.refresh_waifly_config()
        self.set_status(f"Updated profile picture for {display_account_name(self.waifly_config.get('account_username'))}.")

    def remove_account_avatar(self):
        if self.waifly_config.get("identity_mode") != "account" or not clean_text(self.waifly_config.get("account_username")):
            return

        self.waifly_config = update_account_avatar(self.waifly_config, "")
        self.refresh_waifly_config()
        self.set_status(f"Removed profile picture for {display_account_name(self.waifly_config.get('account_username'))}.")

    def logout_account(self):
        username = clean_text(self.waifly_config.get("account_username"))
        if not username:
            return

        self.waifly_config = logout_account_identity(self.waifly_config)
        self.refresh_waifly_config()
        self.set_status(f"Logged out of {display_account_name(username)}.")

    def maybe_prompt_for_local_user_id(self):
        self.refresh_waifly_config()
        if self._user_id_prompt_active:
            return
        if not self.isVisible():
            return
        if not waifly_config_needs_user_id(self.waifly_config):
            return
        if self.waifly_config.get("setup_prompt_suppressed"):
            return

        self._user_id_prompt_active = True
        QtCore.QTimer.singleShot(0, self.prompt_for_local_user_id)

    def copy_local_user_id(self):
        player_id = normalize_player_id(self.local_user_id_input.text() or self.waifly_config.get("user_id"))
        if not player_id:
            self.set_status("Xzen-Network user ID is not configured yet.")
            return

        copy_player_id_to_clipboard(player_id, self.copy_local_user_id_button)
        self.set_status(f"Copied local user ID {player_id}.")

    def showEvent(self, event):
        super().showEvent(event)
        self.maybe_prompt_for_local_user_id()

    def prompt_for_local_user_id(self):
        self.waifly_config = ensure_local_user_id(parent=self, prompt=True)
        self._user_id_prompt_active = False
        self.refresh_local_user_id()
        self.refresh_account_controls()
        if waifly_config_needs_user_id(self.waifly_config):
            self.set_status("Online play setup was skipped. You can finish it later.")
            return

        if self.waifly_config.get("identity_mode") == "account" and self.waifly_config.get("account_username"):
            self.set_status(
                f"Account {display_account_name(self.waifly_config['account_username'])} is ready with player ID {self.waifly_config['user_id']}."
            )
            return

        self.set_status(f"Local player ID {self.waifly_config['user_id']} is ready for online play.")
        self.register_local_player_id()

    def on_worker_finished(self, action: str, payload: dict):
        if action == "exists":
            self.finish_search(payload)
        elif action == "register":
            self.finish_register(payload)

    def on_worker_failed(self, action: str, message: str):
        friendly_message = describe_waifly_error(message)
        if action == "exists":
            self.search_button.setEnabled(True)
            self.search_input.setEnabled(True)
            self.search_worker = None
            self.set_status(f"Search failed: {friendly_message}")
            show_compact_warning(self, "Friend Search Failed", friendly_message)
            return

        if action == "register":
            self.register_worker = None
            self.set_status(f"Could not register local player ID: {friendly_message}")
            print(f"[xzen_service] register failed: {message}")

    def on_download_status(self, message: str):
        self.set_status(message)
        if self.active_download_dialog is not None and self.download_worker is not None:
            self.active_download_dialog.update_install_progress(
                self.active_download_dialog.progress_bar.value(),
                message,
            )

    def on_download_progress(self, value: int, message: str):
        self.set_status(message)
        if self.active_download_dialog is not None:
            self.active_download_dialog.update_install_progress(value, message)

    def on_download_finished(self, player_id: str, mod_count: int, folder: str):
        self.download_worker = None
        save_friends(self.players)
        self.refresh_gallery()
        if self.active_download_dialog is not None and isinstance(self.active_download_mod, dict):
            mod_title = clean_text(self.active_download_mod.get('release_title')) or clean_text(self.active_download_mod.get('name')) or 'selected mod'
            self.active_download_dialog.finish_install(
                self.active_download_mod,
                True,
                f"{mod_title} is installed and ready to load.",
            )
            self.active_download_dialog = None
            self.active_download_mod = None
            self.set_status(f"Downloaded {mod_count} zip file(s) for {player_id} into {folder}.")
            return

        self.set_status(f"Downloaded {mod_count} zip file(s) for {player_id} into {folder}.")
        show_compact_information(
            self,
            "Download Complete",
            f"Downloaded {mod_count} zip file(s) for {player_id}.\n\nSaved to:\n{folder}",
        )

    def on_download_failed(self, player_id: str, message: str):
        self.download_worker = None
        show_popup = True
        if self.active_download_dialog is not None and isinstance(self.active_download_mod, dict):
            mod_title = clean_text(self.active_download_mod.get('release_title')) or clean_text(self.active_download_mod.get('name')) or 'selected mod'
            self.active_download_dialog.finish_install(
                self.active_download_mod,
                False,
                f"Could not install {mod_title}: {message}",
            )
            self.active_download_dialog = None
            self.active_download_mod = None
            show_popup = False
        self.set_status(f"Download failed for {player_id}: {message}")
        if show_popup:
            show_compact_warning(self, "Download Failed", message)

    def finish_search(self, payload: dict):
        searched_value = clean_text(self.search_input.text())
        player_id = normalize_player_id(payload.get("player_id"))
        username = normalize_account_username(payload.get("username"))
        direct_player_id = bool(payload.get("direct_player_id"))
        registry_exists = bool(payload.get("registry_exists"))
        exists = bool(payload.get("exists") and player_id)

        self.search_button.setEnabled(True)
        self.search_input.setEnabled(True)
        self.search_worker = None

        if exists:
            display_name = display_account_name(username) if username else player_id
            if username:
                self.set_status(f"{display_name} is linked to {player_id} on Xzen-Network.")
            elif direct_player_id and not registry_exists:
                self.set_status(f"{player_id} was added directly. It is not listed in the old player registry, but you can still use GitHub mods.")
            else:
                self.set_status(f"{player_id} exists on Xzen-Network.")
            dialog = PlayerFoundDialog(player_id=player_id, mod_count=None, parent=self)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                self.add_player(player_id, 0, display_name, username)
            return

        missing_label = display_account_name(username) if username else searched_value
        self.set_status(f"{missing_label} was not found on Xzen-Network.")
        show_compact_information(
            self,
            "Friend Not Found",
            f"No Xzen-Network account or player was found for {missing_label}.",
        )

    def finish_register(self, payload: dict):
        player_id = normalize_player_id(payload.get("player_id") or self.waifly_config.get("user_id"))
        already_exists = bool(payload.get("already_exists"))
        if player_id:
            self.waifly_config["user_id"] = player_id
            self.refresh_local_user_id()
        self.register_worker = None
        if already_exists:
            self.set_status(f"Local player ID {player_id} is already registered on Xzen-Network.")
        else:
            self.set_status(f"Local player ID {player_id} was registered on Xzen-Network.")

    def set_status(self, message: str):
        self.status_label.setText(clean_text(message))

    def set_player_mod_count(self, player_id: str, mod_count: int):
        normalized_id = normalize_player_id(player_id)
        updated = False
        for player in self.players:
            if player["player_id"] == normalized_id:
                player["mod_count"] = max(0, int(mod_count))
                updated = True
                break
        if updated:
            save_friends(self.players)

    def _default_display_name_for_player(self, player_id: str) -> str:
        normalized_id = normalize_player_id(player_id)
        local_player_id = normalize_player_id(self.waifly_config.get("user_id"))
        if normalized_id and normalized_id == local_player_id:
            username = clean_text(self.waifly_config.get("account_username"))
            if username:
                return display_account_name(username)
        return normalized_id or clean_text(player_id)

    def add_player(self, player_id: str, mod_count: int, display_name: str = "", account_username: str = ""):
        player_id = normalize_player_id(player_id)
        if not player_id:
            return

        incoming_mod_count = max(0, int(mod_count))
        normalized_username = normalize_account_username(account_username)
        preferred_name = (
            clean_text(display_name)
            or (display_account_name(normalized_username) if normalized_username else "")
            or self._default_display_name_for_player(player_id)
        )

        for player in self.players:
            if player["player_id"] == player_id:
                updated = False
                if normalized_username:
                    player["account_username"] = normalized_username
                    updated = True
                current_name = clean_text(player.get("display_name"))
                if preferred_name and (not current_name or current_name == player_id or current_name == self._default_display_name_for_player(player_id)):
                    player["display_name"] = preferred_name
                    updated = True
                current_mod_count = max(0, int(player.get("mod_count", 0)))
                if incoming_mod_count > 0 and current_mod_count <= 0:
                    player["mod_count"] = incoming_mod_count
                    updated = True
                if updated:
                    save_friends(self.players)
                    self.refresh_gallery()
                return

        self.players.append({
            "player_id": player_id,
            "display_name": preferred_name,
            "account_username": normalized_username,
            "mod_count": incoming_mod_count,
            "image_path": None,
        })
        save_friends(self.players)
        self.refresh_gallery()

    def install_community_mod(self, mod: dict, display_name: str = "", account_username: str = "") -> tuple[bool, str]:
        if self.download_worker is not None:
            message = "Another install is already running."
            self.set_status(message)
            return False, message

        player_id = normalize_player_id((mod or {}).get("player_id"))
        if not player_id:
            message = "Cannot install: invalid player ID."
            self.set_status(message)
            return False, message

        base_url = self.waifly_config["api_base_url"]
        resolved_username = normalize_account_username(account_username)
        if not resolved_username:
            try:
                account_lookup = lookup_account_by_player_id(base_url, player_id)
            except Exception:
                account_lookup = {}
            resolved_username = normalize_account_username(
                account_lookup.get("username")
                or account_lookup.get("account_username")
            )

        resolved_name = (
            clean_text(display_name)
            or (display_account_name(resolved_username) if resolved_username else "")
            or resolve_player_display_name(base_url, player_id, friends=self.players)
        )
        self.add_player(player_id, 1, resolved_name, resolved_username)

        normalized_mod = normalize_server_mod(mod, player_id)
        mod_title = clean_text(normalized_mod.get("release_title")) or clean_text(normalized_mod.get("name")) or "selected mod"
        if mod_identity(normalized_mod) in installed_mod_identities(player_id):
            message = f"{mod_title} is already installed."
            self.set_status(message)
            return False, message

        self.active_download_dialog = None
        self.active_download_mod = None
        message = f"Installing {mod_title} for {resolved_name or player_id}..."
        self.set_status(message)
        self.download_worker = PlayerModsDownloadWorker(
            base_url=base_url,
            player_id=player_id,
            mods=[normalized_mod],
            parent=self,
        )
        self.download_worker.status.connect(self.on_download_status)
        self.download_worker.progress.connect(self.on_download_progress)
        self.download_worker.succeeded.connect(self.on_download_finished)
        self.download_worker.failed.connect(self.on_download_failed)
        self.download_worker.start()
        return True, message

    def remove_player(self, player_id: str):
        active_for_player = active_online_runtime_mods_for_player(player_id)
        if active_for_player:
            try:
                restored_mods = disable_all_active_online_mods(player_id)
                if restored_mods:
                    restored_titles = [
                        clean_text(item.get("mod_title")) or normalize_player_id(item.get("player_id")) or "loaded mod"
                        for item in restored_mods
                    ]
                    self.set_status(
                        f"Disabled {len(restored_mods)} loaded online mod(s) before unfriending {player_id}: {', '.join(restored_titles)}."
                    )
            except Exception as e:
                self.set_status(f"Could not disable the active online mods for {player_id}: {str(e) or e.__class__.__name__}")
                show_compact_warning(
                    self,
                    "Unfriend Failed",
                    f"Could not disable the active online mods for {player_id}.\n\n{str(e) or e.__class__.__name__}",
                )
                return
        self.players = [p for p in self.players if p["player_id"] != player_id]
        save_friends(self.players)
        delete_online_profile(player_id)
        self.refresh_gallery()
        self.set_status(f"Removed {player_id} and deleted installed mods.")

    def update_player(self, player_id: str, display_name: str, image_path):
        for player in self.players:
            if player["player_id"] == player_id:
                player["display_name"] = display_name
                player["image_path"] = image_path
                break
        save_friends(self.players)

    def handle_install_player(self, player_id: str):
        if self.mods_list_worker is not None:
            self.set_status("A mod list is already loading.")
            return
        if self.download_worker is not None:
            self.set_status("A profile download is already running.")
            return

        player_id = normalize_player_id(player_id)
        if not player_id:
            self.set_status("Cannot download: invalid player ID.")
            return

        self.clear_github_rate_limit_status()
        self.set_status(f"Loading shared mods for {player_id}...")
        self.mods_list_worker = PlayerModsListWorker(
            base_url=self.waifly_config["api_base_url"],
            player_id=player_id,
            parent=self,
        )
        self.mods_list_worker.succeeded.connect(self.on_mods_list_loaded)
        self.mods_list_worker.failed.connect(self.on_mods_list_failed)
        self.mods_list_worker.start()

    def start_dialog_install(self, player_id: str, mod: dict, dialog: PlayerModsDialog):
        if self.download_worker is not None:
            dialog.update_install_progress(dialog.progress_bar.value(), "Another install is already running.")
            return

        mod_title = clean_text(mod.get('release_title')) or clean_text(mod.get('name')) or 'selected mod'
        dialog.begin_install(mod_title)
        self.active_download_dialog = dialog
        self.active_download_mod = mod
        self.set_status(f"Installing {mod_title} for {player_id}...")
        self.download_worker = PlayerModsDownloadWorker(
            base_url=self.waifly_config["api_base_url"],
            player_id=player_id,
            mods=[mod],
            parent=self,
        )
        self.download_worker.status.connect(self.on_download_status)
        self.download_worker.progress.connect(self.on_download_progress)
        self.download_worker.succeeded.connect(self.on_download_finished)
        self.download_worker.failed.connect(self.on_download_failed)
        self.download_worker.start()

    def start_dialog_delete_local(self, player_id: str, mod: dict, dialog: PlayerModsDialog):
        mod_title = clean_text(mod.get('release_title')) or clean_text(mod.get('name')) or 'selected mod'
        confirm = show_compact_question(
            self,
            "Delete Local Mod",
            f"Delete the local installed copy of {mod_title}?",
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            self.set_status(f"Local delete cancelled for {mod_title}.")
            return

        try:
            if is_online_mod_active(player_id, mod):
                disable_active_online_mod(player_id=player_id, mod=mod)
            deleted_file = delete_installed_online_mod(player_id, mod)
        except Exception as e:
            message = str(e) or e.__class__.__name__
            self.set_status(f"Could not delete local copy of {mod_title}: {message}")
            show_compact_warning(self, "Delete Local Mod Failed", message)
            return

        dialog.finish_local_delete(mod, f"Deleted local copy of {mod_title}.")
        self.refresh_gallery()
        self.set_status(f"Deleted local copy of {mod_title} ({deleted_file}).")

    def start_dialog_delete_shared(self, player_id: str, mod: dict, dialog: PlayerModsDialog):
        mod_title = clean_text(mod.get('release_title')) or clean_text(mod.get('name')) or 'selected mod'
        confirm = show_compact_question(
            self,
            "Delete Shared Mod",
            f"Delete {mod_title} from Xzen-Network?",
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            self.set_status(f"Delete cancelled for {mod_title}.")
            return

        try:
            if is_online_mod_active(player_id, mod):
                disable_active_online_mod(player_id=player_id, mod=mod)
            delete_result = delete_shared_mod(
                self.waifly_config["api_base_url"],
                self.waifly_config.get("admin_key", ""),
                mod,
            )
        except Exception as e:
            message = str(e) or e.__class__.__name__
            self.set_status(f"Could not delete {mod_title}: {message}")
            show_compact_warning(self, "Delete Mod Failed", message)
            return

        release_deleted = bool(delete_result.get("release_deleted"))
        metadata_deleted = bool(delete_result.get("removed_from_metadata"))
        tag_deleted = bool(delete_result.get("tag_deleted"))
        deleted_file = ""
        if mod_identity(mod) in dialog.installed_keys:
            try:
                deleted_file = delete_installed_online_mod(player_id, mod)
            except Exception:
                deleted_file = ""

        outcome_bits = []
        if release_deleted:
            outcome_bits.append("server file deleted")
        if tag_deleted:
            outcome_bits.append("tag removed")
        if metadata_deleted:
            outcome_bits.append("metadata removed")
        if deleted_file:
            outcome_bits.append(f"local file removed: {deleted_file}")
        outcome_text = ", ".join(outcome_bits) if outcome_bits else "delete request completed"

        dialog.finish_shared_delete(mod, f"Deleted {mod_title}: {outcome_text}.")
        if metadata_deleted or release_deleted:
            self.set_player_mod_count(player_id, len(dialog.mods))
        self.set_status(f"Deleted {mod_title}: {outcome_text}.")
        self.refresh_gallery()

    def on_mods_list_loaded(self, player_id: str, mods: object):
        self.mods_list_worker = None
        self.clear_github_rate_limit_status()
        mods = [mod for mod in mods if isinstance(mod, dict)] if isinstance(mods, list) else []
        self.set_player_mod_count(player_id, len(mods))
        self.refresh_gallery()

        if not mods:
            self.set_status(f"No shared mods were found for {player_id}.")
            show_compact_information(self, "No Mods Found", f"{player_id} has no shared mods yet.")
            return

        installed_keys = installed_mod_identities(player_id)
        local_player_id = normalize_player_id(self.waifly_config.get("user_id"))
        is_owner = bool(local_player_id and player_id == local_player_id)
        active_keys = {
            clean_text(active.get("mod_identity"))
            for active in active_online_runtime_mods_for_player(player_id)
            if clean_text(active.get("mod_identity"))
        }
        sharer_name = resolve_player_display_name(
            self.waifly_config["api_base_url"],
            player_id,
            friends=self.players,
        )
        dialog = PlayerModsDialog(
            player_id=player_id,
            sharer_name=sharer_name,
            mods=mods,
            installed_keys=installed_keys,
            allow_delete=is_owner,
            active_keys=active_keys,
            parent=self,
        )
        self.active_mods_dialog = dialog
        dialog.install_requested.connect(lambda mod, pid=player_id, dlg=dialog: self.start_dialog_install(pid, mod, dlg))
        dialog.delete_local_requested.connect(lambda mod, pid=player_id, dlg=dialog: self.start_dialog_delete_local(pid, mod, dlg))
        dialog.delete_requested.connect(lambda mod, pid=player_id, dlg=dialog: self.start_dialog_delete_shared(pid, mod, dlg))
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            if self.active_mods_dialog is dialog:
                self.active_mods_dialog = None
            self.set_status(f"Mod selection closed for {player_id}.")
            return
        if self.active_mods_dialog is dialog:
            self.active_mods_dialog = None

        mod = dialog.selected_mod()
        if not isinstance(mod, dict):
            self.set_status("No mod was selected.")
            return

        mod_title = clean_text(mod.get('release_title')) or clean_text(mod.get('name')) or 'selected mod'
        if dialog.action == "load":
            if mod_identity(mod) not in installed_keys:
                self.set_status(f"{mod_title} is not installed yet.")
                return
            try:
                load_result = toggle_online_mod_load(player_id, mod)
                if clean_text(load_result.get("action")) == "conflict":
                    confirm = show_compact_question(
                        self,
                        "Mod Conflict",
                        f"{clean_text(load_result.get('message'))}\n\nContinue and replace the conflicting loaded mod(s)?",
                    )
                    if confirm != QtWidgets.QMessageBox.Yes:
                        self.set_status(f"Kept the existing loaded modpack(s). {mod_title} was not loaded.")
                        return
                    load_result = toggle_online_mod_load(player_id, mod, allow_replace=True)
                restarted_game = False
                if clean_text(load_result.get("action")) == "loaded":
                    restarted_game = restart_game_if_running()
                    load_result["restarted_game"] = restarted_game
            except Exception as e:
                message = str(e) or e.__class__.__name__
                self.set_status(f"Could not load {mod_title}: {message}")
                show_compact_warning(self, "Load Mod Failed", message)
                return

            action = clean_text(load_result.get("action")) or "loaded"
            message = clean_text(load_result.get("message")) or f"Loaded {mod_title}."
            if action == "loaded" and bool(load_result.get("restarted_game")):
                message = f"{message} The game was restarted because it was already running."
            self.set_status(message)
            if action == "disabled":
                show_compact_information(self, "Online Mod Disabled", message)
            else:
                loaded_path = clean_text(load_result.get("modded_path"))
                show_compact_information(
                    self,
                    "Mod Loaded",
                    f"{message}\n\nSource folder:\n{loaded_path}" if loaded_path else message,
                )
            return

        if mod_identity(mod) in installed_keys:
            self.set_status(f"{mod_title} is already installed.")
            return

        self.set_status(f"Installing {mod_title} for {player_id}...")
        self.download_worker = PlayerModsDownloadWorker(
            base_url=self.waifly_config["api_base_url"],
            player_id=player_id,
            mods=[mod],
            parent=self,
        )
        self.download_worker.status.connect(self.on_download_status)
        self.download_worker.succeeded.connect(self.on_download_finished)
        self.download_worker.failed.connect(self.on_download_failed)
        self.download_worker.start()

    def on_mods_list_failed(self, player_id: str, message: object):
        self.mods_list_worker = None
        if isinstance(message, dict) and message.get("type") == "github_rate_limit":
            reset_at = message.get("reset_at")
            self.start_github_rate_limit_status(player_id, reset_at)
            dialog = GitHubRateLimitDialog(player_id=player_id, reset_at=reset_at, parent=self)
            dialog.exec_()
            return

        raw_message = str(message)
        friendly_message = describe_waifly_error(raw_message)
        self.set_status(f"Could not load mods for {player_id}: {friendly_message}")
        show_compact_warning(self, "Load Mods Failed", friendly_message)

    def refresh_gallery(self):
        changed = False
        local_player_id = normalize_player_id(self.waifly_config.get("user_id"))
        for player in self.players:
            player_id = normalize_player_id(player.get("player_id"))
            account_username = normalize_account_username(player.get("account_username"))
            current_name = clean_text(player.get("display_name"))

            if account_username:
                preferred_name = display_account_name(account_username)
                if preferred_name and (not current_name or current_name == player_id):
                    player["display_name"] = preferred_name
                    current_name = preferred_name
                    changed = True

            if player_id != local_player_id:
                continue
            default_name = self._default_display_name_for_player(player_id)
            if default_name and (not current_name or current_name == player_id):
                player["display_name"] = default_name
                changed = True
        if changed:
            save_friends(self.players)

        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self.players:
            empty = QtWidgets.QLabel("No friends added yet.")
            empty.setStyleSheet(f"""
                color: {TEXT_DIM};
                font-size: 14px;
                background: transparent;
            """)
            self.gallery_layout.addWidget(empty, 0, 0)
            self.gallery_layout.setRowStretch(1, 1)
            self.gallery_layout.setColumnStretch(self.GRID_COLUMNS, 1)
            return

        for index, player in enumerate(self.players):
            row = index // self.GRID_COLUMNS
            col = index % self.GRID_COLUMNS

            card = PlayerCard(
                player_id=player["player_id"],
                mod_count=player["mod_count"],
                display_name=player["display_name"],
                image_path=player["image_path"],
                installed=online_profile_has_content(player["player_id"]),
                is_owner=player["player_id"] == normalize_player_id(self.waifly_config.get("user_id")),
            )
            card.removed.connect(self.remove_player)
            card.changed.connect(self.update_player)
            card.install_clicked.connect(self.handle_install_player)

            self.gallery_layout.addWidget(card, row, col)

        last_row = (len(self.players) - 1) // self.GRID_COLUMNS + 1
        self.gallery_layout.setRowStretch(last_row, 1)
        self.gallery_layout.setColumnStretch(self.GRID_COLUMNS, 1)
