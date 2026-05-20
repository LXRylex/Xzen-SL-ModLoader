from __future__ import annotations

from pathlib import Path
import hashlib
import os
import re
import sys
import time
import uuid

try:
    import winreg
except ImportError:
    winreg = None


PLAYER_ID_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PLAYER_ID_BODY_LENGTH = 8
ACCOUNT_USERNAME_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9._-]{1,22}[a-z0-9])?")
ACCOUNT_PASSWORD_MIN_LENGTH = 6
ACCOUNT_ID_NAMESPACE = "xzen-waifly-account-v1"
ACCOUNT_HASH_NAMESPACE = "xzen-waifly-password-v1"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(os.path.abspath(os.path.dirname(__file__))).parent.parent.parent.parent


def clean_text(value) -> str:
    return str(value or "").strip()


def normalize_player_id(value: str) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if not text.startswith("#"):
        text = f"#{text}"
    text = text.upper()
    return text if re.fullmatch(r"#(?:[0-9]{4}|[A-Z0-9]{8})", text) else ""


def normalize_identity_mode(value) -> str:
    return "account" if clean_text(value).lower() == "account" else "device"


def normalize_account_username(value: str) -> str:
    username = clean_text(value).lower()
    return username if ACCOUNT_USERNAME_PATTERN.fullmatch(username) else ""


def display_account_name(value: str) -> str:
    username = clean_text(value)
    if not username:
        return ""
    return username[:1].upper() + username[1:]


def validate_account_credentials(username: str, password: str, *, require_confirm: str | None = None) -> tuple[str, str]:
    normalized_username = normalize_account_username(username)
    password_text = str(password or "")
    confirm_text = "" if require_confirm is None else str(require_confirm)

    if not normalized_username:
        raise ValueError("Choose a username with 3-24 letters, numbers, dots, dashes, or underscores.")
    if len(password_text) < ACCOUNT_PASSWORD_MIN_LENGTH:
        raise ValueError(f"Choose a password with at least {ACCOUNT_PASSWORD_MIN_LENGTH} characters.")
    if require_confirm is not None and password_text != confirm_text:
        raise ValueError("Passwords do not match.")
    return normalized_username, password_text


def base36_encode(number: int) -> str:
    if number <= 0:
        return "0"

    chars = []
    value = number
    while value:
        value, remainder = divmod(value, 36)
        chars.append(PLAYER_ID_ALPHABET[remainder])
    return "".join(reversed(chars))


def account_password_hash(username: str, password: str) -> str:
    normalized_username = normalize_account_username(username)
    if not normalized_username or not str(password or ""):
        return ""

    salt = f"{ACCOUNT_HASH_NAMESPACE}|{normalized_username}".encode("utf-8", errors="replace")
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8", errors="replace"),
        salt,
        120000,
    )
    return digest.hex()


def derive_account_user_id(username: str, password: str) -> str:
    normalized_username = normalize_account_username(username)
    password_text = str(password or "")
    if not normalized_username or not password_text:
        return ""

    source = f"{ACCOUNT_ID_NAMESPACE}|{normalized_username}|{password_text}"
    fingerprint = hashlib.sha256(source.encode("utf-8", errors="replace")).hexdigest()
    encoded = base36_encode(int(fingerprint, 16)).upper()
    body = encoded[-PLAYER_ID_BODY_LENGTH:].rjust(PLAYER_ID_BODY_LENGTH, "0")
    return f"#{body}"


def utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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
