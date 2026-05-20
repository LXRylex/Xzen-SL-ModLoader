import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

# ── repo paths ────────────────────────────────────────────────────────────────
THIS_FILE   = Path(__file__).resolve()
SOURCE_DIR  = THIS_FILE.parents[2]                   # .../source
BACKUP_DIR  = SOURCE_DIR / "mods" / "backup" / "emoticon"
PROFILE_DIR = SOURCE_DIR / "profile" / "user_data"
PATHS_JSON  = PROFILE_DIR / "paths.json"
USER_LOG    = PROFILE_DIR / "user.logs"             # consolidated log

# ── helpers ──────────────────────────────────────────────────────────────────
def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def iter_files(root: Path) -> List[Path]:
    if root.is_file():
        return [root]
    return [p for p in root.rglob("*") if p.is_file()]

def write_txt(where: Path, folder_name: str, mode: str,
              restored: List[str], skipped: List[str]) -> None:
    ensure_dir(where)
    txt = where / f"{folder_name}.txt"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"[{now}] {folder_name} - {mode}", f"Path: {where}", ""]
    if restored:
        lines.append("RESTORED FILES:")
        lines += [f"  - {p}" for p in restored]
        lines.append("")
    if skipped:
        lines.append("SKIPPED (metadata or error):")
        lines += [f"  - {p}" for p in skipped]
    with txt.open("w", encoding="utf-8", errors="replace") as f:
        f.write("\n".join(lines))

# ── logging ──────────────────────────────────────────────────────────────────
def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_reset(header_lines: List[str]) -> None:
    ensure_dir(PROFILE_DIR)
    with USER_LOG.open("w", encoding="utf-8", errors="replace") as f:
        for line in header_lines:
            f.write(line.rstrip() + "\n")

def _log(level: str, msg: str) -> None:
    with USER_LOG.open("a", encoding="utf-8", errors="replace") as f:
        f.write(f"[{_ts()}] [{level.lower()}] {msg}\n")

def info(msg: str) -> None:    _log("info", msg)
def warn(msg: str) -> None:    _log("warn", msg)
def success(msg: str) -> None: _log("success", msg)
def failed(msg: str) -> None:  _log("failed", msg)

# ── main ─────────────────────────────────────────────────────────────────────
def main():
    print("=== EmoteIconRecover: start ===")

    # header
    log_reset([
        f"[{_ts()}] [info] EmoteIconRecover run",
        f"[{_ts()}] [info] mode: restore (merge)",
        f"[{_ts()}] [info] backup source: {BACKUP_DIR}",
        f"[{_ts()}] [info] user log     : {USER_LOG}",
    ])

    # load paths.json
    if not PATHS_JSON.exists():
        msg = f"Missing paths.json at {PATHS_JSON}"
        failed(msg); raise FileNotFoundError(msg)

    try:
        with PATHS_JSON.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        msg = f"Failed to read JSON: {PATHS_JSON} ({e})"
        failed(msg); raise

    assetbundles_dir = cfg.get("assetbundles_dir")
    if not assetbundles_dir:
        msg = "paths.json missing 'assetbundles_dir'"
        failed(msg); raise KeyError(msg)

    EMO_DIR = Path(assetbundles_dir) / "emoticon"
    if not EMO_DIR.exists():
        msg = f"'emoticon' folder not found at: {EMO_DIR}"
        failed(msg); raise FileNotFoundError(msg)

    if not BACKUP_DIR.exists():
        msg = f"Backup folder missing: {BACKUP_DIR}"
        failed(msg); raise FileNotFoundError(msg)

    info(f"game emoticon folder: {EMO_DIR}")

    # one-time cleanup: purge any legacy _summary.log files in backups
    purged = 0
    for old in BACKUP_DIR.rglob("_summary.log"):
        try:
            old.unlink()
            purged += 1
        except Exception as e:
            warn(f"could not remove legacy _summary.log at {old} ({e})")
    if purged:
        info(f"purged legacy _summary.log files: {purged}")

    # walk all files under backup/emoticon and restore to <AssetBundles>/emoticon
    backups = iter_files(BACKUP_DIR)
    if not backups:
        info("no emoticon backups found.")
        print("No emoticon backups found.")
        print(f"user log: {USER_LOG}")
        return

    restored_rel: List[str] = []
    skipped_rel: List[str]  = []

    for bfile in backups:
        rel = bfile.relative_to(BACKUP_DIR).as_posix()

        # skip metadata created by install/backup
        if rel in {"emoticon.txt", "user.logs"}:
            warn(f"skip metadata '{rel}'")
            skipped_rel.append(rel)
            continue

        dst_file = EMO_DIR / rel
        ensure_dir(dst_file.parent)
        try:
            shutil.copy2(bfile, dst_file)
            restored_rel.append(rel)
        except Exception as e:
            err_line = f"{rel}  [error: {e}]"
            failed(f"failed copy '{rel}' -> '{dst_file}' ({e})")
            skipped_rel.append(err_line)

    # receipt at destination root
    write_txt(EMO_DIR, "emoticon", "original-restored", restored_rel, skipped_rel)

    # structured log
    success(f"RESTORE emoticon: restored={len(restored_rel)}, skipped={len(skipped_rel)} -> {EMO_DIR}")
    if restored_rel:
        info(f"restored file list ({len(restored_rel)}):")
        for r in restored_rel:
            success(f"+ {r}")
    if skipped_rel:
        warn(f"skipped items ({len(skipped_rel)}):")
        for s in skipped_rel:
            warn(f"- {s}")

    print("\n=== EmoteIconRecover: complete ===")
    print(f"Emoticon at: {EMO_DIR}")
    print(f"User log (overwritten each run): {USER_LOG}")
    success("run complete")

if __name__ == "__main__":
    main()
