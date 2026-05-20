import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

THIS_FILE = Path(__file__).resolve()
SOURCE_DIR = THIS_FILE.parents[2]
BACKUP_DIR = SOURCE_DIR / "mods" / "backup" / "custom_stages"
PROFILE_DIR = SOURCE_DIR / "profile" / "user_data"
STATE_JSON = PROFILE_DIR / "stage_mod_state.json"
USER_LOG = PROFILE_DIR / "user.logs"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_reset(header_lines: List[str]) -> None:
    ensure_dir(PROFILE_DIR)
    with USER_LOG.open("w", encoding="utf-8", errors="replace") as handle:
        for line in header_lines:
            handle.write(line.rstrip() + "\n")


def _log(level: str, message: str) -> None:
    with USER_LOG.open("a", encoding="utf-8", errors="replace") as handle:
        handle.write(f"[{_ts()}] [{level.lower()}] {message}\n")


def info(message: str) -> None:
    _log("info", message)


def warn(message: str) -> None:
    _log("warn", message)


def success(message: str) -> None:
    _log("success", message)


def failed(message: str) -> None:
    _log("failed", message)


def clean_text(value) -> str:
    return str(value or "").strip()


def load_state() -> dict:
    if not STATE_JSON.exists():
        msg = f"Stage mod state was not found: {STATE_JSON}"
        failed(msg)
        raise FileNotFoundError(msg)
    try:
        raw = json.loads(STATE_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        msg = f"Failed to read stage mod state: {STATE_JSON} ({exc})"
        failed(msg)
        raise
    if not isinstance(raw, dict):
        msg = f"Invalid stage mod state payload in {STATE_JSON}"
        failed(msg)
        raise ValueError(msg)
    return raw


def main():
    print("=== StageSwapRecover: start ===")
    log_reset([
        f"[{_ts()}] [info] StageSwapRecover run",
        f"[{_ts()}] [info] mode: restore stage mods",
        f"[{_ts()}] [info] backups     : {BACKUP_DIR}",
        f"[{_ts()}] [info] state file  : {STATE_JSON}",
        f"[{_ts()}] [info] user log    : {USER_LOG}",
    ])

    state = load_state()
    entries = [item for item in state.get("entries", []) if isinstance(item, dict)]
    if not entries:
        msg = "No stage mod entries were recorded in the stage state file."
        failed(msg)
        raise RuntimeError(msg)

    restored_count = 0
    removed_count = 0

    for item in reversed(entries):
        target_path = Path(clean_text(item.get("target_path")))
        if not str(target_path):
            continue

        had_original = bool(item.get("had_original"))
        backup_path_text = clean_text(item.get("backup_path"))
        if had_original:
            if not backup_path_text:
                msg = f"Restore data is missing for {target_path}"
                failed(msg)
                raise RuntimeError(msg)
            backup_path = Path(backup_path_text)
            if not backup_path.exists():
                msg = f"Restore backup was not found: {backup_path}"
                failed(msg)
                raise FileNotFoundError(msg)
            ensure_dir(target_path.parent)
            shutil.copy2(backup_path, target_path)
            restored_count += 1
            success(f"restored {target_path}")
        elif target_path.exists():
            target_path.unlink()
            removed_count += 1
            success(f"removed {target_path}")
        else:
            warn(f"target already missing: {target_path}")

    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)
    if STATE_JSON.exists():
        STATE_JSON.unlink()

    print("\n=== StageSwapRecover: complete ===")
    print(f"Restored originals: {restored_count}")
    print(f"Removed new files : {removed_count}")
    print(f"User log: {USER_LOG}")
    success(f"run complete: restored={restored_count}, removed={removed_count}")


if __name__ == "__main__":
    main()
