import json
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List

THIS_FILE   = Path(__file__).resolve()
SOURCE_DIR  = THIS_FILE.parents[2]
MODDED_DIR  = SOURCE_DIR / "mods" / "modded" / "emoticon"
BACKUP_DIR  = SOURCE_DIR / "mods" / "backup" / "emoticon"
PROFILE_DIR = SOURCE_DIR / "profile" / "user_data"
PATHS_JSON  = PROFILE_DIR / "paths.json"
USER_LOG    = PROFILE_DIR / "user.logs"

# ── helpers ──────────────────────────────────────────────────────────────────
def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def md5sum(p: Path) -> str:
    h = hashlib.md5()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()

def is_different(src: Path, dst: Path) -> bool:
    if not dst.exists():
        return True
    try:
        if src.stat().st_size != dst.stat().st_size:
            return True
    except Exception:
        return True
    try:
        return md5sum(src) != md5sum(dst)
    except Exception:
        return True

def iter_files(root: Path) -> List[Path]:
    if root.is_file():
        return [root]
    return [p for p in root.rglob("*") if p.is_file()]

def write_txt(where: Path, folder_name: str, mode: str,
              changed_backed: List[str], changed_skipped: List[str],
              new_files: List[str], same_files: List[str]) -> None:
    ensure_dir(where)
    txt = where / f"{folder_name}.txt"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"[{now}] {folder_name} - {mode}", f"Path: {where}", ""]
    if changed_backed:
        lines.append("OVERWRITTEN (backed up originals now):")
        lines += [f"  - {p}" for p in changed_backed]
        lines.append("")
    if changed_skipped:
        lines.append("OVERWRITTEN (backup already existed — not copied again):")
        lines += [f"  - {p}" for p in changed_skipped]
        lines.append("")
    if new_files:
        lines.append("NEW FILES (no original):")
        lines += [f"  - {p}" for p in new_files]
        lines.append("")
    if same_files:
        lines.append("UNCHANGED (identical bytes):")
        lines += [f"  - {p}" for p in same_files]
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
    print("=== EmoteIconSwapEngine (merge, no duplicate backups): start ===")

    # header
    log_reset([
        f"[{_ts()}] [info] EmoteIconSwapEngine run",
        f"[{_ts()}] [info] mode: merge + first-time backups only",
        f"[{_ts()}] [info] modded source: {MODDED_DIR}",
        f"[{_ts()}] [info] backups     : {BACKUP_DIR}",
        f"[{_ts()}] [info] user log    : {USER_LOG}",
    ])

    # load config
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

    # destination = <AssetBundles>/emoticon
    EMO_DST_DIR = Path(assetbundles_dir) / "emoticon"
    ensure_dir(EMO_DST_DIR)

    # source = mods/modded/emoticon (must exist)
    if not MODDED_DIR.exists():
        msg = f"Modded emoticon folder missing: {MODDED_DIR}"
        failed(msg); raise FileNotFoundError(msg)

    info(f"dest emoticon folder: {EMO_DST_DIR}")

    # collect files under emoticon root (all folders/files)
    src_files = iter_files(MODDED_DIR)
    if not src_files:
        info("no modded files found under 'mods/modded/emoticon'. nothing to do.")
        print("No modded files found.")
        print(f"user log: {USER_LOG}")
        return

    changed_backed: List[str] = []
    changed_skipped: List[str] = []
    new_rel: List[str] = []
    same_rel: List[str] = []

    for src_file in src_files:
        rel = src_file.relative_to(MODDED_DIR).as_posix()
        # skip stray pack receipts/logs
        if rel in {"user.logs", "_summary.log"} or rel.endswith(".txt"):
            warn(f"skip metadata '{rel}'")
            continue

        dst_file = EMO_DST_DIR / rel
        ensure_dir(dst_file.parent)

        if dst_file.exists():
            if is_different(src_file, dst_file):
                backup_file = BACKUP_DIR / rel
                if backup_file.exists():
                    changed_skipped.append(rel)
                else:
                    ensure_dir(backup_file.parent)
                    try:
                        shutil.copy2(dst_file, backup_file)
                        changed_backed.append(rel)
                    except Exception as e:
                        warn(f"backup failed for '{rel}' ({e}); will not duplicate")
                        changed_skipped.append(f"{rel}  [backup-error: {e}]")
            else:
                same_rel.append(rel)
        else:
            new_rel.append(rel)

        try:
            shutil.copy2(src_file, dst_file)
        except Exception as e:
            failed(f"failed to copy '{rel}' -> '{dst_file}' ({e})")

    # receipts
    if changed_backed or changed_skipped:
        write_txt(BACKUP_DIR, "emoticon",
                  "original-backups (first-time only)",
                  changed_backed, changed_skipped, [], [])
    write_txt(EMO_DST_DIR, "emoticon",
              "modded-installed (merge, no duplicate backups)",
              changed_backed, changed_skipped, new_rel, same_rel)

    total_changed = len(changed_backed) + len(changed_skipped)
    success(f"emoticon: changed={total_changed} "
            f"(backed_now={len(changed_backed)}, backup_preexisted={len(changed_skipped)}), "
            f"new={len(new_rel)}, same={len(same_rel)}")

    if changed_backed:
        info(f"backed up originals now ({len(changed_backed)}):")
        for r in changed_backed:
            success(f"+backup {r}")
    if changed_skipped:
        warn(f"already had backups ({len(changed_skipped)}):")
        for r in changed_skipped:
            warn(f"~skip   {r}")
    if new_rel:
        info(f"new files ({len(new_rel)}):")
        for r in new_rel:
            success(f"+new    {r}")
    if same_rel:
        info(f"unchanged files ({len(same_rel)}):")
        for r in same_rel:
            info(f"=same   {r}")

    print("\n=== EmoteIconSwapEngine: complete ===")
    print(f"Backups at: {BACKUP_DIR}")
    print(f"Emoticon at: {EMO_DST_DIR}")
    print(f"User log (overwritten each run): {USER_LOG}")
    success("run complete")

if __name__ == "__main__":
    main()
