# steam_verify.py
# Checks if Steam is running. If not, launches error.py (custom popup).
# If yes, triggers Steam's built-in file verification for AppID 1352080 via:
#   steam://validate/1352080

import os
import sys
import subprocess
from pathlib import Path

APPID = "1352080"

HERE = Path(__file__).resolve().parent
ERROR_PY = HERE / "error.py"

def is_windows() -> bool:
    return os.name == "nt"

def steam_running_windows() -> bool:
    # 1) Reliable: PowerShell Get-Process
    try:
        CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "if (Get-Process -Name steam -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }",
        ]
        r = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
        if r.returncode == 0:
            return True
    except Exception:
        pass

    # 2) Fallback: tasklist (case-insensitive)
    try:
        out = subprocess.check_output(
            ["tasklist", "/NH", "/FO", "CSV"],
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).lower()
        return "steam.exe" in out
    except Exception:
        return False

def show_error_popup(title: str, message: str) -> None:
    if not ERROR_PY.exists():
        print(f"[error] {message} (and error.py not found at {ERROR_PY})")
        return

    args = [sys.executable, str(ERROR_PY), title, message]

    if is_windows():
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        subprocess.Popen(args, creationflags=creationflags)
    else:
        subprocess.Popen(args)

def open_steam_validate(appid: str) -> None:
    uri = f"steam://validate/{appid}"
    if is_windows():
        os.startfile(uri)  # type: ignore[attr-defined]
    else:
        opener = "xdg-open" if sys.platform.startswith("linux") else "open"
        subprocess.Popen([opener, uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main() -> int:
    if not APPID.isdigit():
        show_error_popup("Invalid AppID", f"AppID must be numeric. Got: {APPID}")
        return 2

    if is_windows():
        if not steam_running_windows():
            show_error_popup("Steam Required", "Steam is not running.\n\nPlease start Steam first, then try again.")
            return 1

    try:
        open_steam_validate(APPID)
        return 0
    except Exception as e:
        show_error_popup("Verify Failed", f"Could not trigger Steam validation.\n\n{e}")
        return 3

if __name__ == "__main__":
    raise SystemExit(main())
