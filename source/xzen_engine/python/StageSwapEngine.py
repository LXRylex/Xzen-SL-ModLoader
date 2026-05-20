import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

THIS_FILE = Path(__file__).resolve()
SOURCE_DIR = THIS_FILE.parents[2]
MODDED_DIR = SOURCE_DIR / "mods" / "modded" / "custom_stages"
BACKUP_DIR = SOURCE_DIR / "mods" / "backup" / "custom_stages"
PROFILE_DIR = SOURCE_DIR / "profile" / "user_data"
PATHS_JSON = PROFILE_DIR / "paths.json"
STATE_JSON = PROFILE_DIR / "stage_mod_state.json"
USER_LOG = PROFILE_DIR / "user.logs"

SKIP_FILE_NAMES = {"destination.json", "user.logs", "_summary.log"}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def iter_files(root: Path) -> List[Path]:
    if root.is_file():
        return [root]
    return [path for path in root.rglob("*") if path.is_file()]


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


def load_paths_config() -> dict:
    if not PATHS_JSON.exists():
        msg = f"Missing paths.json at {PATHS_JSON}"
        failed(msg)
        raise FileNotFoundError(msg)
    try:
        with PATHS_JSON.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        msg = f"Failed to read JSON: {PATHS_JSON} ({exc})"
        failed(msg)
        raise
    if not isinstance(data, dict):
        msg = f"Invalid JSON payload in {PATHS_JSON}"
        failed(msg)
        raise ValueError(msg)
    return data


def compute_stage_destinations() -> tuple[Path, Path]:
    cfg = load_paths_config()
    assetbundles_dir = clean_text(cfg.get("assetbundles_dir"))
    if not assetbundles_dir:
        msg = "paths.json missing 'assetbundles_dir'"
        failed(msg)
        raise KeyError(msg)

    assetbundles_path = Path(assetbundles_dir)
    scenes_dir = assetbundles_path / "map" / "scenes"
    if not scenes_dir.exists():
        msg = f"Stage scenes folder not found at: {scenes_dir}"
        failed(msg)
        raise FileNotFoundError(msg)

    smash_data_dir = assetbundles_path.parent.parent
    mods_dir = smash_data_dir / "Mods"
    return scenes_dir, mods_dir


def normalize_path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def collect_stage_roots() -> List[Path]:
    if not MODDED_DIR.exists():
        msg = f"Modded custom stages folder missing: {MODDED_DIR}"
        failed(msg)
        raise FileNotFoundError(msg)

    stage_dirs = sorted([path for path in MODDED_DIR.iterdir() if path.is_dir()], key=lambda path: path.name.lower())
    loose_files = [
        path for path in MODDED_DIR.iterdir()
        if path.is_file()
        and path.name.lower() not in SKIP_FILE_NAMES
        and path.suffix.lower() != ".txt"
    ]

    roots = list(stage_dirs)
    if loose_files:
        roots.append(MODDED_DIR)
    if not roots:
        msg = f"No stage mod files were found in {MODDED_DIR}"
        failed(msg)
        raise FileNotFoundError(msg)
    return roots


def build_stage_plan() -> List[dict]:
    scenes_dir, mods_dir = compute_stage_destinations()
    ensure_dir(mods_dir)

    by_target: dict[str, dict] = {}
    for stage_root in collect_stage_roots():
        stage_name = stage_root.name if stage_root != MODDED_DIR else "custom_stages"
        for source_path in iter_files(stage_root):
            lower_name = source_path.name.lower()
            if lower_name in SKIP_FILE_NAMES or source_path.suffix.lower() == ".txt":
                continue

            if lower_name == "chartrial02":
                target_path = scenes_dir / source_path.name
                backup_rel = Path(stage_name) / "scenes" / source_path.name
            elif lower_name.endswith(".ress"):
                target_path = mods_dir / source_path.name
                backup_rel = Path(stage_name) / "mods" / source_path.name
            else:
                continue

            by_target[normalize_path_key(target_path)] = {
                "stage_name": stage_name,
                "source_path": str(source_path),
                "target_path": str(target_path),
                "backup_rel": backup_rel.as_posix(),
            }

    plan = list(by_target.values())
    if not plan:
        msg = f"No supported stage files were found in {MODDED_DIR}"
        failed(msg)
        raise FileNotFoundError(msg)
    return plan


def save_state(state: dict) -> None:
    ensure_dir(STATE_JSON.parent)
    STATE_JSON.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    print("=== StageSwapEngine: start ===")
    log_reset([
        f"[{_ts()}] [info] StageSwapEngine run",
        f"[{_ts()}] [info] mode: install stage mods",
        f"[{_ts()}] [info] modded source: {MODDED_DIR}",
        f"[{_ts()}] [info] backups     : {BACKUP_DIR}",
        f"[{_ts()}] [info] state file  : {STATE_JSON}",
        f"[{_ts()}] [info] user log    : {USER_LOG}",
    ])

    if STATE_JSON.exists():
        msg = "Stage mods already look active. Run disable_stage.bat before enabling again."
        failed(msg)
        raise RuntimeError(msg)

    plan = build_stage_plan()
    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)
    ensure_dir(BACKUP_DIR)

    state_entries: List[dict] = []
    applied_count = 0
    backed_count = 0
    new_count = 0

    try:
        for entry in plan:
            source_path = Path(entry["source_path"])
            target_path = Path(entry["target_path"])
            backup_path = BACKUP_DIR / entry["backup_rel"]
            had_original = target_path.exists()

            ensure_dir(target_path.parent)
            if had_original:
                ensure_dir(backup_path.parent)
                shutil.copy2(target_path, backup_path)
                backed_count += 1
                info(f"backup -> {backup_path}")
            else:
                new_count += 1
                info(f"new target -> {target_path}")

            shutil.copy2(source_path, target_path)
            applied_count += 1
            success(f"installed {source_path.name} -> {target_path}")
            state_entries.append(
                {
                    "stage_name": entry["stage_name"],
                    "source_path": str(source_path),
                    "target_path": str(target_path),
                    "backup_path": str(backup_path) if had_original else "",
                    "had_original": had_original,
                }
            )

        save_state(
            {
                "enabled_at": _ts(),
                "entries": state_entries,
            }
        )
    except Exception:
        for item in reversed(state_entries):
            target_path = Path(item["target_path"])
            backup_path_text = clean_text(item.get("backup_path"))
            if item.get("had_original") and backup_path_text:
                backup_path = Path(backup_path_text)
                if backup_path.exists():
                    ensure_dir(target_path.parent)
                    shutil.copy2(backup_path, target_path)
            elif target_path.exists():
                target_path.unlink()
        if BACKUP_DIR.exists():
            shutil.rmtree(BACKUP_DIR)
        if STATE_JSON.exists():
            STATE_JSON.unlink()
        raise

    print("\n=== StageSwapEngine: complete ===")
    print(f"Applied files: {applied_count}")
    print(f"Backed up originals: {backed_count}")
    print(f"New targets created: {new_count}")
    print(f"User log: {USER_LOG}")
    success(
        f"run complete: applied={applied_count}, backed_up={backed_count}, new_targets={new_count}"
    )


if __name__ == "__main__":
    main()
