"""VAJB update 1.0 - update from inside the app via git (RULES.md V2). Based on Ghostcut update.py.

    import update
    update.init(APP_DIR, version_file="app/version.py", launcher="myapp.pyw")
    update.check() -> {"ok", "behind", "version", "changes": [...], "local": [...]}
    update.pull()  -> {"ok", "out", "changed"}
    update.restart()
Only app code changes; data/ is in .gitignore and is never touched.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import applog

NOWIN = 0x08000000 if sys.platform == "win32" else 0                      # CREATE_NO_WINDOW
DETACH = 0x00000008 | 0x00000200 if sys.platform == "win32" else 0        # DETACHED_PROCESS | NEW_PROCESS_GROUP
log = applog.get("update")
APP_DIR: Path = Path(".")
VERSION_FILE = "version.py"
LAUNCHER = "app.pyw"


def init(app_dir, version_file="version.py", launcher="app.pyw"):
    global APP_DIR, VERSION_FILE, LAUNCHER
    APP_DIR, VERSION_FILE, LAUNCHER = Path(app_dir), version_file, launcher


def git_exe():
    for c in (shutil.which("git"), r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files (x86)\Git\cmd\git.exe"):
        if c and Path(c).exists():
            return c
    return None


def git(*args, timeout=120):
    exe = git_exe()
    if not exe:
        raise RuntimeError("Git nije pronađen na ovom računaru.")
    r = subprocess.run([exe, *args], cwd=APP_DIR, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, creationflags=NOWIN)
    return r.returncode, (r.stdout + r.stderr).strip()


def check():
    code, out = git("fetch", "--quiet")
    if code:
        log.warning("fetch failed: %s", out)
        return {"ok": False, "error": out[-300:]}
    _, n = git("rev-list", "--count", "HEAD..@{u}")
    _, subj = git("log", "--format=%s", "HEAD..@{u}")
    _, st = git("status", "--porcelain", "--untracked-files=no")
    _, remote = git("show", f"@{{u}}:{VERSION_FILE}")
    m = re.search(r'VERSION\s*=\s*"([^"]+)"', remote or "")
    return {"ok": True, "behind": int(n) if n.strip().isdigit() else 0, "version": m.group(1) if m else "",
            "changes": [l.strip()[:400] for l in subj.splitlines() if l.strip()][:10],
            "local": [x[3:] for x in st.splitlines() if x.strip()]}


def pull():
    _, before = git("rev-parse", "HEAD")
    code, out = git("pull", "--ff-only", timeout=300)
    if code:
        log.error("pull failed: %s", out[-500:])
        return {"ok": False, "out": out}
    _, after = git("rev-parse", "HEAD")
    res = {"ok": True, "out": out, "changed": before != after}
    if before != after:
        _, files = git("diff", "--name-only", before, after)
        if any(f.startswith("requirements") for f in files.splitlines()):
            py = Path(sys.executable)
            if py.name.lower() == "pythonw.exe":
                py = py.with_name("python.exe")
            r = subprocess.run([str(py), "-m", "pip", "install", "-q", "-r", str(APP_DIR / "requirements.txt")],
                               cwd=APP_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=900, creationflags=NOWIN)
            res["out"] += "\n\npip: " + ((r.stdout + r.stderr).strip()[-800:] or "ok")
            res["pip_error"] = bool(r.returncode)
        log.info("updated %s -> %s (%d files)", before[:7], after[:7], len(files.splitlines()))
    return res


def restart(*extra: str):
    """Starts the launcher with --restart in the background; it stops this server and starts the new code.
    extra: e.g. "--tiho" when no window is open (background update)."""
    log.info("restart %s", " ".join(extra))
    subprocess.Popen([sys.executable, str(APP_DIR / LAUNCHER), "--restart", *extra], cwd=APP_DIR,
                     creationflags=NOWIN | DETACH, close_fds=True)
