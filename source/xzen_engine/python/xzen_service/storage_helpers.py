from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class StorageHelper:
    friends_json: Path
    waifly_accounts_json: Path
    ensure_dirs: callable
    clean_text: callable
    normalize_player_id: callable
    normalize_account_username: callable
    validate_account_credentials: callable
    account_password_hash: callable
    utc_now_iso: callable
    device_fingerprint: callable
    normalize_identity_mode: callable

    def normalize_friend_entries(self, items) -> list[dict]:
        if not isinstance(items, list):
            return []

        cleaned = []
        for item in items:
            if not isinstance(item, dict):
                continue
            player_id = self.normalize_player_id(item.get("player_id"))
            if not player_id:
                continue
            cleaned.append({
                "player_id": player_id,
                "display_name": str(item.get("display_name", "")).strip() or player_id,
                "account_username": self.normalize_account_username(item.get("account_username")),
                "mod_count": int(item.get("mod_count", 0)),
                "image_path": item.get("image_path", None),
            })
        return cleaned

    def load_local_accounts(self) -> dict[str, dict]:
        self.ensure_dirs()
        if not self.waifly_accounts_json.exists():
            return {}

        try:
            raw = json.loads(self.waifly_accounts_json.read_text(encoding="utf-8"))
        except Exception:
            return {}

        items = raw.get("accounts", []) if isinstance(raw, dict) else []
        if not isinstance(items, list):
            return {}

        accounts: dict[str, dict] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            username = self.normalize_account_username(item.get("username"))
            if not username:
                continue
            accounts[username] = {
                "username": username,
                "user_id": self.normalize_player_id(item.get("user_id")),
                "password_hash": self.clean_text(item.get("password_hash")),
                "created_at": self.clean_text(item.get("created_at")),
                "last_login_at": self.clean_text(item.get("last_login_at")),
                "last_device_fingerprint": self.clean_text(item.get("last_device_fingerprint")),
                "avatar_path": self.clean_text(item.get("avatar_path")),
                "password_updated_at": self.clean_text(item.get("password_updated_at")),
                "friends": self.normalize_friend_entries(item.get("friends")),
            }
        return accounts

    def save_local_accounts(self, accounts: dict[str, dict]) -> None:
        self.ensure_dirs()
        rows = []
        for username in sorted(accounts):
            record = accounts.get(username) or {}
            rows.append({
                "username": username,
                "user_id": self.normalize_player_id(record.get("user_id")),
                "password_hash": self.clean_text(record.get("password_hash")),
                "created_at": self.clean_text(record.get("created_at")),
                "last_login_at": self.clean_text(record.get("last_login_at")),
                "last_device_fingerprint": self.clean_text(record.get("last_device_fingerprint")),
                "avatar_path": self.clean_text(record.get("avatar_path")),
                "password_updated_at": self.clean_text(record.get("password_updated_at")),
                "friends": self.normalize_friend_entries(record.get("friends")),
            })
        self.waifly_accounts_json.write_text(
            json.dumps({"accounts": rows}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def remember_local_account(self, username: str, user_id: str, password_hash_value: str) -> None:
        normalized_username = self.normalize_account_username(username)
        normalized_user_id = self.normalize_player_id(user_id)
        if not normalized_username or not normalized_user_id or not self.clean_text(password_hash_value):
            return

        accounts = self.load_local_accounts()
        existing = accounts.get(normalized_username, {})
        accounts[normalized_username] = {
            "username": normalized_username,
            "user_id": normalized_user_id,
            "password_hash": self.clean_text(password_hash_value),
            "created_at": self.clean_text(existing.get("created_at")) or self.utc_now_iso(),
            "last_login_at": self.utc_now_iso(),
            "last_device_fingerprint": self.device_fingerprint(),
            "avatar_path": self.clean_text(existing.get("avatar_path")),
            "password_updated_at": self.clean_text(existing.get("password_updated_at")),
            "friends": self.normalize_friend_entries(existing.get("friends")),
        }
        self.save_local_accounts(accounts)

    def set_local_account_avatar(self, username: str, avatar_path: str) -> None:
        normalized_username = self.normalize_account_username(username)
        if not normalized_username:
            return

        accounts = self.load_local_accounts()
        existing = accounts.get(normalized_username)
        if not isinstance(existing, dict):
            return

        existing["avatar_path"] = self.clean_text(avatar_path)
        accounts[normalized_username] = existing
        self.save_local_accounts(accounts)

    def set_local_account_friends(self, username: str, friends: list[dict]) -> None:
        normalized_username = self.normalize_account_username(username)
        if not normalized_username:
            return

        accounts = self.load_local_accounts()
        existing = accounts.get(normalized_username)
        if not isinstance(existing, dict):
            return

        updated = existing.copy()
        updated["friends"] = self.normalize_friend_entries(friends)
        accounts[normalized_username] = updated
        self.save_local_accounts(accounts)

    def restore_local_account_friends(self, username: str) -> list[dict]:
        normalized_username = self.normalize_account_username(username)
        if not normalized_username:
            return []

        accounts = self.load_local_accounts()
        existing = accounts.get(normalized_username)
        if not isinstance(existing, dict):
            return []
        return self.normalize_friend_entries(existing.get("friends"))

    def set_local_account_password(self, username: str, new_password: str) -> dict:
        normalized_username, password_text = self.validate_account_credentials(username, new_password)
        accounts = self.load_local_accounts()
        existing = accounts.get(normalized_username)
        if not isinstance(existing, dict):
            raise ValueError(f"Account was not found for username: {normalized_username}")

        updated = existing.copy()
        updated["password_hash"] = self.account_password_hash(normalized_username, password_text)
        updated["password_updated_at"] = self.utc_now_iso()
        accounts[normalized_username] = updated
        self.save_local_accounts(accounts)
        return updated

    def load_friends(self):
        self.ensure_dirs()
        if not self.friends_json.exists():
            return []

        try:
            data = json.loads(self.friends_json.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return self.normalize_friend_entries(data)
        except Exception as e:
            print(f"[xzen_service] failed to load friends: {e}")

        return []

    def save_friends(self, players, current_config_loader=None):
        self.ensure_dirs()
        try:
            normalized_players = self.normalize_friend_entries(players)
            self.friends_json.write_text(
                json.dumps(normalized_players, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            if callable(current_config_loader):
                current_config = current_config_loader()
                if self.normalize_identity_mode(current_config.get("identity_mode")) == "account":
                    username = self.normalize_account_username(current_config.get("account_username"))
                    if username:
                        self.set_local_account_friends(username, normalized_players)
        except Exception as e:
            print(f"[xzen_service] failed to save friends: {e}")

    def clear_active_friends(self):
        self.ensure_dirs()
        try:
            self.friends_json.write_text("[]", encoding="utf-8")
        except Exception as e:
            print(f"[xzen_service] failed to clear active friends: {e}")
