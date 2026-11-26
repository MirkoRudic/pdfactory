"""Updates for installed copies (PDFactory-Setup.exe): no git there, new versions come as GitHub Releases.

check()  -> {"ok", "behind", "version", "url"}   latest release vs running version
apply()  -> downloads the new Setup.exe into data/tmp and runs it silently; the installer closes this app,
            replaces the files and starts PDFactory again (see packaging/setup.iss, [Run] ... WizardSilent).
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import applog
import version

log = applog.get("selfupdate")
REPO = "MirkoRudic/pdfactory"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
_latest: dict = {}


def _num(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def check() -> dict:
    global _latest
    try:
        req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json", "User-Agent": "PDFactory"})
        with urllib.request.urlopen(req, timeout=10) as r:
            rel = json.loads(r.read())
    except Exception as e:
        log.warning("release check: %s", e)
        return {"ok": False}
    ver = (rel.get("tag_name") or "").lstrip("v")
    asset = next((a for a in rel.get("assets", []) if a.get("name", "").lower().endswith(".exe")), None)
    if not ver or not asset:
        return {"ok": True, "behind": 0, "version": version.VERSION}
    _latest = {"version": ver, "url": asset["browser_download_url"], "size": asset.get("size", 0)}
    behind = 1 if _num(ver) > _num(version.VERSION) else 0
    return {"ok": True, "behind": behind, "version": ver, "changes": [rel.get("name") or ""]}


def clean(folder: Path):
    """At start: installers of versions that are already installed (a downloaded newer one stays for later)."""
    for p in Path(folder).glob("PDFactory-Setup-*.exe"):
        m = re.search(r"Setup-([\d.]+)\.exe$", p.name)
        if not m or _num(m.group(1)) <= _num(version.VERSION):
            try:
                p.unlink()
            except OSError:
                pass


def download(tmp_dir: Path) -> Path | None:
    """Downloads the latest Setup once (kept in data/updates until it is installed). None = nothing new or failed."""
    if not _latest:
        r = check()
        if not r.get("ok") or not _latest:
            return None
    if _num(_latest["version"]) <= _num(version.VERSION):
        return None
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    dst = Path(tmp_dir) / f"PDFactory-Setup-{_latest['version']}.exe"
    if dst.exists() and (not _latest.get("size") or dst.stat().st_size == _latest["size"]):
        return dst
    part = dst.with_suffix(".part")
    log.info("downloading %s", _latest["url"])
    try:
        req = urllib.request.Request(_latest["url"], headers={"User-Agent": "PDFactory"})
        with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
    except Exception:
        log.exception("download failed")
        part.unlink(missing_ok=True)
        return None
    if _latest.get("size") and part.stat().st_size != _latest["size"]:
        log.error("download size %s != %s", part.stat().st_size, _latest["size"])
        part.unlink(missing_ok=True)
        return None
    os.replace(part, dst)
    log.info("downloaded %s", dst.name)
    return dst


def ready(tmp_dir: Path) -> str:
    """Version of a downloaded installer waiting to be installed, or ''."""
    best = ""
    for p in Path(tmp_dir).glob("PDFactory-Setup-*.exe"):
        m = re.search(r"Setup-([\d.]+)\.exe$", p.name)
        if m and _num(m.group(1)) > _num(version.VERSION) and (not best or _num(m.group(1)) > _num(best)):
            best = m.group(1)
    return best


def run(setup: Path, tmp_dir: Path, relaunch: str = "window"):
    """Runs the installer silently once this process has exited. relaunch: window = start the app again
    (the open window reloads), tiho = start it in the tray only, none = do not start it (the user quit).
    Started right away, the installer found the app still running, could not close it (no window) and
    aborted with suppressed message boxes (measured 26.11.2026, Windows 10): so a hidden PowerShell waits
    for this PID first."""
    app_dir = Path(__file__).resolve().parents[1]
    args = [str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", f"/DIR={app_dir}",
            f"/RELAUNCH={relaunch}", f"/LOG={Path(tmp_dir) / 'setup.log'}"]   # the log says what went wrong, if anything
    log.info("running %s (after pid %s exits)", " ".join(args), os.getpid())
    q = lambda s: "'" + str(s).replace("'", "''") + "'"
    ps = (f"Wait-Process -Id {os.getpid()} -Timeout 60 -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500; "
          f"Start-Process -FilePath {q(setup)} -ArgumentList @({','.join(q(a) for a in args[1:])})")
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-Command", ps]
    flags = 0x00000008 | 0x00000200 | 0x08000000 | 0x01000000 if sys.platform == "win32" else 0   # DETACHED | NEW_GROUP | NO_WINDOW | BREAKAWAY_FROM_JOB
    try:
        subprocess.Popen(cmd, cwd=str(app_dir), creationflags=flags, close_fds=True)
    except OSError:                      # breakaway not allowed in this job: without it
        subprocess.Popen(cmd, cwd=str(app_dir), creationflags=flags & ~0x01000000, close_fds=True)


def apply(tmp_dir: Path, relaunch: str = "window") -> dict:
    setup = download(tmp_dir)
    if not setup:
        return {"ok": False, "error": "The update could not be downloaded. Check the internet connection."}
    run(setup, tmp_dir, relaunch)
    return {"ok": True, "changed": True, "installer": True}
