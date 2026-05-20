from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import re

try:
    import winreg
except ImportError:
    winreg = None


@dataclass
class PathsHelper:
    paths_json: Path
    steam_app_id: int
    game_hints: tuple[str, ...]
    ensure_dirs: callable

    def _clean_text(self, value) -> str:
        return str(value or "").strip()

    def _paths_payload(self, assetbundles_dir: str = "", game_exe: str = "") -> dict:
        return {
            "assetbundles_dir": self._clean_text(assetbundles_dir),
            "game_exe": self._clean_text(game_exe),
        }

    def save_paths_config(self, data: dict) -> dict:
        self.ensure_dirs()
        payload = self._paths_payload(data.get("assetbundles_dir", ""), data.get("game_exe", ""))
        self.paths_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def _steam_root(self) -> Path | None:
        if winreg is not None:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                    value, _ = winreg.QueryValueEx(key, "SteamPath")
                candidate = Path(value)
                if candidate.exists():
                    return candidate
            except Exception:
                pass

        candidates = [
            Path("C:/Program Files (x86)/Steam"),
            Path("C:/Program Files/Steam"),
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Steam",
            Path(os.environ.get("PROGRAMFILES", "")) / "Steam",
        ]
        for candidate in candidates:
            if str(candidate) and candidate.exists():
                return candidate
        return None

    def _steam_libraries(self, steam_root: Path) -> list[Path]:
        libraries = [steam_root]
        library_file = steam_root / "steamapps" / "libraryfolders.vdf"
        if library_file.exists():
            try:
                text = library_file.read_text(encoding="utf-8", errors="ignore")
                paths = re.findall(r'"path"\s*"([^"]+)"', text, flags=re.IGNORECASE)
                for path_text in paths:
                    candidate = Path(path_text.replace("\\\\", "\\"))
                    if candidate.exists():
                        libraries.append(candidate)
            except Exception:
                pass

        unique_paths = []
        seen = set()
        for candidate in libraries:
            try:
                resolved = str(candidate.resolve()).lower()
            except Exception:
                resolved = str(candidate).lower()
            if resolved not in seen:
                seen.add(resolved)
                unique_paths.append(candidate)
        return unique_paths

    def _parse_acf_value(self, acf_file: Path, key: str) -> str:
        try:
            text = acf_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
        match = re.search(rf'"{re.escape(key)}"\s*"([^"]+)"', text, flags=re.IGNORECASE)
        return match.group(1) if match else ""

    def discover_game_paths(self) -> dict:
        steam_root = self._steam_root()
        if not steam_root:
            return self._paths_payload()

        libraries = self._steam_libraries(steam_root)
        game_dir = None
        for library in libraries:
            manifest = library / "steamapps" / f"appmanifest_{self.steam_app_id}.acf"
            if not manifest.exists():
                continue
            install_dir = self._parse_acf_value(manifest, "installdir")
            if not install_dir:
                continue
            candidate = library / "steamapps" / "common" / install_dir
            if candidate.exists():
                game_dir = candidate
                break
            fallback = library / "steamapps" / "common" / "Smash Legends"
            if fallback.exists():
                game_dir = fallback
                break

        if not game_dir or not game_dir.exists():
            return self._paths_payload()

        found_exe = ""
        executables = list(game_dir.glob("*.exe")) or list(game_dir.rglob("*.exe"))
        preferred = [exe for exe in executables if any(hint in exe.name.lower() for hint in self.game_hints)]
        selected_exe = preferred[0] if preferred else (executables[0] if executables else None)
        if selected_exe is not None:
            found_exe = str(selected_exe)

        found_bundles = ""
        data_dirs = list(game_dir.glob("*_Data"))
        for data_dir in data_dirs:
            candidate = data_dir / "StreamingAssets" / "AssetBundles"
            if candidate.exists() and candidate.is_dir():
                found_bundles = str(candidate)
                break

        return self._paths_payload(found_bundles, found_exe)

    def ensure_paths_config(self) -> dict:
        self.ensure_dirs()

        existing = {}
        if self.paths_json.exists():
            try:
                raw = json.loads(self.paths_json.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    existing = raw
            except Exception:
                existing = {}

        assetbundles_dir = self._clean_text(existing.get("assetbundles_dir"))
        game_exe = self._clean_text(existing.get("game_exe"))

        if assetbundles_dir and not Path(assetbundles_dir).expanduser().exists():
            assetbundles_dir = ""
        if game_exe and not Path(game_exe).expanduser().exists():
            game_exe = ""

        if not assetbundles_dir or not game_exe:
            detected = self.discover_game_paths()
            if not assetbundles_dir:
                assetbundles_dir = self._clean_text(detected.get("assetbundles_dir"))
            if not game_exe:
                game_exe = self._clean_text(detected.get("game_exe"))

        payload = self._paths_payload(assetbundles_dir, game_exe)
        if (not self.paths_json.exists()) or existing != payload:
            self.save_paths_config(payload)
        return payload

    def load_paths_config(self) -> dict:
        data = self.ensure_paths_config()
        assetbundles_dir = self._clean_text(data.get("assetbundles_dir"))
        if not assetbundles_dir:
            raise RuntimeError("Game paths are not configured yet. Open Settings and use Auto-locate Game Paths.")
        assetbundles_path = Path(assetbundles_dir).expanduser()
        if not assetbundles_path.exists():
            raise RuntimeError(f"Configured AssetBundles folder was not found: {assetbundles_path}\nOpen Settings and refresh the game paths.")

        game_exe = self._clean_text(data.get("game_exe"))
        if not game_exe:
            raise RuntimeError("Game executable is not configured yet. Open Settings and use Auto-locate Game Paths.")
        game_exe_path = Path(game_exe).expanduser()
        if not game_exe_path.exists():
            raise RuntimeError(f"Configured game executable was not found: {game_exe_path}\nOpen Settings and refresh the game paths.")
        return data

    def game_exe_path(self) -> Path:
        game_exe = self._clean_text(self.load_paths_config().get("game_exe"))
        return Path(game_exe).expanduser()

    def game_assetbundles_dir(self) -> Path:
        return Path(self.load_paths_config()["assetbundles_dir"]).expanduser()

    def game_ui_target_path(self, assetbundles_dir: Path) -> Path:
        return assetbundles_dir / "ui"

    def default_stage_destinations(self, assetbundles_dir: Path) -> tuple[Path, Path]:
        data_dir = assetbundles_dir.parent.parent
        return assetbundles_dir / "map" / "scenes", data_dir / "Mods"
