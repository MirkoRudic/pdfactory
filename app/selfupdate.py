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
    """Installers of earlier updates are deleted at the next start."""
    for p in Path(folder).glob("PDFactory-Setup-*.exe"):
        try:
            p.unlink()
        except OSError:
            pass


def apply(tmp_dir: Path) -> dict:
    if not _latest:
        r = check()
        if not r.get("ok") or not _latest:
            return {"ok": False, "error": "The update could not be found."}
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    dst = Path(tmp_dir) / f"PDFactory-Setup-{_latest['version']}.exe"
    log.info("downloading %s", _latest["url"])
    try:
        req = urllib.request.Request(_latest["url"], headers={"User-Agent": "PDFactory"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
    except Exception:
        log.exception("download failed")
        return {"ok": False, "error": "Download failed. Check the internet connection."}
    if _latest.get("size") and dst.stat().st_size != _latest["size"]:
        log.error("download size %s != %s", dst.stat().st_size, _latest["size"])
        return {"ok": False, "error": "Download failed. Try again."}
    app_dir = Path(__file__).resolve().parents[1]
    args = [str(dst), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", f"/DIR={app_dir}"]
    log.info("running %s", " ".join(args))
    flags = 0x00000008 | 0x00000200 if sys.platform == "win32" else 0     # DETACHED_PROCESS | NEW_PROCESS_GROUP
    subprocess.Popen(args, cwd=str(tmp_dir), creationflags=flags, close_fds=True)
    return {"ok": True, "changed": True, "installer": True}
