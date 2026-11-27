"""PDFactory web server (127.0.0.1 only, P2)."""
import hashlib
import os
import sys
import threading
import time
import uuid
from pathlib import Path

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))
APP_DIR = APP.parent
DATA = APP_DIR / "data"

import applog  # noqa: E402

applog.setup(DATA / "logs", "pdfactory")
import fonts  # noqa: E402
import hardexit  # noqa: E402
import pdfops  # noqa: E402
import printing  # noqa: E402
import selfupdate  # noqa: E402
import localguard  # noqa: E402
import settings  # noqa: E402
import tempdir  # noqa: E402
import update  # noqa: E402
import version  # noqa: E402
import winsetup  # noqa: E402
from fastapi import Body, FastAPI, File, Request, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response  # noqa: E402

log = applog.get("server")
PORT = int(os.environ.get("PDFACTORY_PORT", "8802"))
DEFAULTS = {
    "theme": "dark",
    "ocr_lang": "srp+srp_latn+eng",
    "tessdata": "",
    "recent": [],
    "was_default": False,
    "backup_keep": 20,
    "last_dir": "",
    "last_printer": "",
}
settings.init(DATA / "settings.json", DEFAULTS)
tempdir.init(DATA / "tmp")
pdfops.init_session(DATA / "session")
update.init(APP_DIR, version_file="app/version.py", launcher="PDFactory.pyw")
applog.auto_trim(settings.load().get("log_auto_trim_mb", 500))
threading.Thread(target=lambda: fonts.init(DATA / "fonts.json"), name="fontovi", daemon=True).start()
selfupdate.clean(DATA / "updates")

app = FastAPI()
localguard.install(app, log)          # F9: only our own window (no DNS rebinding, no CSRF)
app.state.quit = None
app.state.stop = None
ASK_QUIT = False               # tray menu "Quit": the window asks for confirmation (P4)
SEEN = {"t": 0.0}               # last poll of an open app window (V5: updates install only when no window is open)
INBOX: list[dict] = []          # files opened from outside (double click on a PDF) waiting for the window
_inbox_lock = threading.Lock()


def err(msg: str, code=400):
    return JSONResponse({"error": msg}, status_code=code)


@app.exception_handler(pdfops.UserError)
async def _user_error(_req: Request, e: pdfops.UserError):
    return err(str(e))


@app.exception_handler(Exception)
async def _any_error(req: Request, e: Exception):
    log.error("%s %s", req.method, req.url.path, exc_info=e)
    return err("Something went wrong. Details are in the log.", 500)


# ---------- page ----------

def _hash(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()[:8]


@app.get("/", response_class=HTMLResponse)
def index():
    html = (APP / "static" / "index.html").read_text(encoding="utf-8")
    for f in ("base.css", "app.css", "dialog.js", "app.js"):          # UI11
        html = html.replace(f'"{f}"', f'"/static/{f}?v={_hash(APP / "static" / f)}"')
    html = html.replace('"/logo.png"', f'"/logo.png?v={_hash(APP_DIR / "assets" / "pdfactory_256.png")}"')   # UI11
    s = settings.load()
    theme = s.get("theme") if s.get("theme") in ("dark", "light") else "dark"
    html = html.replace('data-theme="dark"', f'data-theme="{theme}"')
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.get("/static/{name}")
def static(name: str):
    p = (APP / "static" / name).resolve()
    if p.parent != (APP / "static").resolve() or not p.exists():
        return Response(status_code=404)
    return FileResponse(p, headers={"Cache-Control": "max-age=31536000"})


@app.get("/favicon.ico")
def favicon():
    return FileResponse(APP_DIR / "assets" / "pdfactory.ico")


@app.get("/logo.png")
def logo():
    return FileResponse(APP_DIR / "assets" / "pdfactory_256.png", headers={"Cache-Control": "max-age=3600"})


@app.get("/health")
def health():
    return {"app": "pdfactory", "version": version.VERSION, "pid": os.getpid()}


# ---------- opening ----------

def _remember(src: pdfops.Source):
    if not src.path:
        return
    s = settings.load()
    rec = [r for r in s["recent"] if r.get("path") != src.path]
    rec.insert(0, {"path": src.path, "name": src.name, "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    s["recent"] = rec[:12]
    s["last_dir"] = str(Path(src.path).parent)
    settings.save(s)


@app.post("/api/open")
def open_files(body: dict = Body(...)):
    paths = body.get("paths") or []
    out = []
    for p in paths:
        src = pdfops.open_path(p)
        _remember(src)
        out.append(src.info())
    return {"docs": out}


@app.post("/api/pick-open")
def pick_open():
    paths = winsetup.ask_open(settings.load().get("last_dir") or None)
    if not paths:
        return {"docs": []}
    return open_files({"paths": paths})


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    src = pdfops.open_bytes(data, file.filename or "dokument.pdf")
    return src.info()


@app.post("/api/open-external")
def open_external(body: dict = Body(...)):
    """Called by the launcher when a PDF is double-clicked while the app runs."""
    with _inbox_lock:
        INBOX.append({"path": body["path"], "at": time.time()})
    return {"ok": True}


@app.get("/api/inbox")
def inbox():
    global ASK_QUIT
    SEEN["t"] = time.time()
    ask, ASK_QUIT = ASK_QUIT, False
    with _inbox_lock:
        items = INBOX[:]
        INBOX.clear()
    docs, errors = [], []
    for it in items:
        try:
            src = pdfops.open_path(it["path"])
            _remember(src)
            docs.append(src.info())
        except pdfops.UserError as e:
            errors.append(f"{Path(it['path']).name}: {e}")
    return {"docs": docs, "errors": errors, "askQuit": ask, "pid": os.getpid()}


@app.get("/api/recent")
def recent():
    rec = [r for r in settings.load()["recent"] if Path(r["path"]).exists()]
    return {"recent": rec}


@app.post("/api/close/{src_id}")
def close(src_id: str):
    pdfops.close(src_id)
    return {"ok": True}


@app.get("/api/src/{src_id}")
def src_info(src_id: str):
    return pdfops.get(src_id).info()


@app.get("/api/src/{src_id}/page/{n}.png")
def page_png(src_id: str, n: int, w: int = 800, rot: int = 0):
    png = pdfops.render(src_id, n, min(max(w, 40), 4000), rot % 360)
    return Response(png, media_type="image/png", headers={"Cache-Control": "max-age=600"})


@app.get("/api/src/{src_id}/page/{n}/text")
def page_text(src_id: str, n: int):
    return pdfops.page_text(src_id, n)


@app.get("/api/src/{src_id}/page/{n}/fixtext")
def fix_text(src_id: str, n: int, x0: float, y0: float, x1: float, y1: float, text: str = ""):
    """Text for 'fix text': what the line looks like (OCR) when the PDF's own text is wrongly mapped."""
    import difflib
    import unicodedata
    td = _tessdata()
    if not td:
        return {"text": text, "source": "pdf"}
    have = set(pdfops.tess_langs(td))
    # one script per line: with srp_latn+srp together Tesseract mixes alphabets ("Rok" read as Cyrillic "Рок")
    cyr = any("\u0400" <= c <= "\u04ff" for c in text)
    lang = "+".join(l for l in (("srp" if cyr else "srp_latn"), "eng") if l in have) or "eng"
    try:
        ocr = pdfops.ocr_rect(src_id, n, (x0, y0, x1, y1), lang, td)
    except Exception:
        log.exception("fixtext ocr")
        return {"text": text, "source": "pdf"}

    def plain(t):
        t = unicodedata.normalize("NFKD", t.replace("đ", "dj").replace("Đ", "Dj"))
        return "".join(c for c in t if not unicodedata.combining(c)).lower().replace(" ", "")
    same = difflib.SequenceMatcher(None, plain(ocr), plain(text)).ratio()
    bad_chars = any(c in text for c in "\ufffd\x83") or any(ord(c) < 32 for c in text)
    use_ocr = bool(ocr) and (bad_chars or (same > 0.7 and ocr != text))
    log.info("fixtext ratio %.2f ocr=%s", same, use_ocr)
    return {"text": ocr if use_ocr else text, "source": "ocr" if use_ocr else "pdf"}


@app.get("/api/src/{src_id}/page/{n}/forms")
def page_forms(src_id: str, n: int):
    return {"fields": pdfops.page_forms(src_id, n)}


@app.get("/api/src/{src_id}/search")
def search(src_id: str, q: str):
    return {"hits": pdfops.search(src_id, q) if q.strip() else []}


# ---------- images & fonts ----------

@app.post("/api/image")
async def image(file: UploadFile = File(...)):
    from PIL import Image
    import io
    data = await file.read()
    try:
        im = Image.open(io.BytesIO(data))
        w, h = im.size
    except Exception:
        return err("This image can't be opened.")
    return {"id": pdfops.add_image(data), "w": w, "h": h}


@app.get("/api/image/{iid}")
def image_get(iid: str):
    data = pdfops.image_data(iid)
    if data is None:
        return Response(status_code=404)
    return Response(data, media_type="image/*", headers={"Cache-Control": "max-age=86400"})


@app.get("/api/fonts")
def font_list():
    return {"fonts": fonts.families(), "default": fonts.default_family()}


@app.get("/api/font")
def font_file(name: str, s: str = "r"):
    f = fonts.file_for(name, s)
    if not f:
        return Response(status_code=404)
    return FileResponse(f, headers={"Cache-Control": "max-age=86400"})


# ---------- saving ----------

def _compose(body):
    return pdfops.compose(body["items"], body.get("objects"), body.get("forms"))


@app.post("/api/save")
def save(body: dict = Body(...)):
    """body: items, objects, forms, path (None = ask), ask (bool)."""
    target = body.get("path")
    if body.get("ask") or not target:
        target = winsetup.ask_save(target or str(Path(settings.load().get("last_dir") or Path.home()) / body.get("name", "dokument.pdf")))
        if not target:
            return {"cancelled": True}
    with applog.timed("save", f"save {target}"):
        doc = _compose(body)
        saved = pdfops.save_doc(doc, target, DATA / "rezerva", settings.load().get("backup_keep", 20))
        doc.close()
    src = pdfops.open_path(saved)
    _remember(src)
    for old in set(it["src"] for it in body["items"]):
        if old != src.id and body.get("closeOld", True):
            pdfops.close(old)
    return {"doc": src.info(), "path": saved}


@app.post("/api/extract")
def extract(body: dict = Body(...)):
    """Selected pages to a new file (asks where)."""
    target = winsetup.ask_save(body.get("suggest"))
    if not target:
        return {"cancelled": True}
    doc = _compose(body)
    saved = pdfops.save_doc(doc, target)
    doc.close()
    return {"path": saved}


@app.post("/api/split")
def split(body: dict = Body(...)):
    """body: parts: [[item,...], ...], base name. Files go to a chosen folder as <name>_1.pdf, _2..."""
    folder = winsetup.ask_folder(body.get("dir") or settings.load().get("last_dir"))
    if not folder:
        return {"cancelled": True}
    stem = Path(body.get("name", "dokument")).stem
    paths = []
    for i, part in enumerate(body["parts"], 1):
        doc = pdfops.compose(part, body.get("objects"), body.get("forms"))
        # a file of the same name is replaced, but its old version goes to data/rezerva, as on Save
        paths.append(pdfops.save_doc(doc, str(Path(folder) / f"{stem}_{i}.pdf"), DATA / "rezerva",
                                     settings.load().get("backup_keep", 20)))
        doc.close()
    return {"paths": paths, "folder": folder}


@app.post("/api/compose-preview")
def compose_preview(body: dict = Body(...)):
    """Workspace -> temporary source (used for print preview / OCR of a composed document)."""
    doc = _compose(body)
    src = pdfops.open_bytes(doc.tobytes(), body.get("name", "dokument.pdf"))
    doc.close()
    return src.info()


@app.post("/api/show-in-folder")
def show_in_folder(body: dict = Body(...)):
    winsetup.show_in_folder(body["path"])
    return {"ok": True}


# ---------- OCR ----------

def _tessdata():
    return pdfops.find_tessdata(settings.load().get("tessdata", ""))


@app.get("/api/ocr/info")
def ocr_info():
    td = _tessdata()
    return {"tessdata": td, "langs": pdfops.tess_langs(td), "lang": settings.load()["ocr_lang"]}


@app.post("/api/ocr/{src_id}")
def ocr(src_id: str, body: dict = Body(default={})):
    td = _tessdata()
    if not td:
        return err("Text recognition languages not found (tessdata).")
    have = pdfops.tess_langs(td)
    # no language choice for the user: Serbian (both scripts) and English, whatever is installed
    lang = "+".join(l for l in ("srp_latn", "srp", "eng") if l in have) or "+".join(have[:3])
    ff = fonts.file_for(fonts.default_family(), "r")
    threading.Thread(target=pdfops.ocr_source, args=(src_id, lang, td, ff), name="ocr", daemon=True).start()
    return {"ok": True, "lang": lang}


@app.get("/api/ocr/{src_id}/status")
def ocr_status(src_id: str):
    s = pdfops.get(src_id)
    return s.ocr or {"state": "nema"}


# ---------- printing ----------

@app.get("/api/printers")
def printers():
    r = printing.printers()
    last = settings.load().get("last_printer")
    if last in r["printers"]:
        r["default"] = last
    r["available"] = printing.available()
    return r


@app.post("/api/print")
def do_print(body: dict = Body(...)):
    if not printing.available():
        return err("Printing works only on Windows with pywin32.")
    o = body.get("options", {})
    doc = _compose(body)
    pages = pdfops.parse_ranges(o.get("pages", ""), doc.page_count)
    if not pages:
        return err("No pages selected.")
    if len(pages) != doc.page_count:
        doc.select(pages)
    doc = pdfops.n_up(doc, int(o.get("perSheet", 1)))
    s = settings.load()
    s["last_printer"] = o.get("printer", "")
    settings.save(s)
    job = uuid.uuid4().hex[:8]
    o["title"] = body.get("name", "PDFactory")
    printing.start(job, doc, o)
    log.info("print job %s: %d sheets on %s", job, doc.page_count, o.get("printer"))
    return {"job": job}


@app.get("/api/print/{job}")
def print_status(job: str):
    return printing.JOBS.get(job, {"state": "nema"})


# ---------- settings, log, windows, update ----------

@app.get("/api/settings")
def get_settings():
    s = settings.load()
    td = _tessdata()
    return {"theme": s["theme"], "ocr_lang": s["ocr_lang"], "tessdata": td, "langs": pdfops.tess_langs(td),
            "version": version.label(), "log_mb": applog.size_mb(),
            "autostart": winsetup.autostart_enabled(), "is_default": winsetup.is_default(),
            "windows": winsetup.WIN, "git": (APP_DIR / ".git").exists() or winsetup.INSTALLED,
            "installed": winsetup.INSTALLED}


@app.post("/api/settings")
def set_settings(body: dict = Body(...)):
    s = settings.load()
    if body.get("theme") in ("dark", "light"):   # goes into index.html as is: only known values
        s["theme"] = body["theme"]
    for k in ("ocr_lang", "tessdata"):
        if k in body:
            s[k] = body[k]
    settings.save(s)
    if "autostart" in body:
        winsetup.set_autostart(bool(body["autostart"]))
    return get_settings()


@app.get("/api/default-check")
def default_check():
    """Was PDFactory the default PDF program and something (e.g. an Adobe update) took it over? (F3)"""
    s = settings.load()
    now = winsetup.is_default()
    lost = s.get("was_default") and not now
    if lost:
        log.warning("PDFactory is no longer the default PDF program (now: %s)", winsetup.current_default())
    if now != s.get("was_default"):
        s["was_default"] = now
        settings.save(s)
    ask = (DATA / "ask_default").exists()          # installer option "Make PDFactory the default": asked inside the app
    if ask and now:
        (DATA / "ask_default").unlink(missing_ok=True)
        ask = False
    lost = lost and not ask
    return {"is_default": now, "lost": bool(lost), "ask": ask, "windows": winsetup.WIN}


@app.post("/api/default-ask-done")
def default_ask_done():
    (DATA / "ask_default").unlink(missing_ok=True)
    return {"ok": True}


@app.post("/api/default-app")
def default_app():
    winsetup.open_default_apps()
    return {"ok": True}


@app.get("/api/log")
def get_log(days: int = 2, problems: bool = False, q: str = ""):
    return {"lines": applog.read(days, problems, q or None), "mb": applog.size_mb()}


@app.post("/api/log/delete")
def delete_log(body: dict = Body(...)):
    n = applog.delete_older_than(int(body.get("days", 30)))
    return {"deleted": n, "mb": applog.size_mb()}


def _disk_version() -> str:
    import re
    m = re.search(r'VERSION\s*=\s*"([^"]+)"', (APP / "version.py").read_text(encoding="utf-8"))
    return m.group(1) if m else ""


@app.get("/api/update")
def update_check():
    if winsetup.INSTALLED:                       # installed copy: new versions are GitHub Releases
        r = selfupdate.check()
        r["ready"] = selfupdate.ready(DATA / "updates")
        return r
    try:
        r = update.check()
    except Exception as e:
        log.warning("update check: %s", e)
        r = {"ok": False}
    # code on disk can be newer than the running server (pulled or copied while it ran): that also needs a restart
    disk = _disk_version()
    r["running"] = version.VERSION
    r["restart"] = bool(disk) and disk != version.VERSION
    if r["restart"]:
        r["ok"] = True
        if not r.get("behind"):
            r["version"] = disk
    return r


@app.post("/api/update")
def update_pull():
    if winsetup.INSTALLED:
        r = selfupdate.apply(DATA / "updates")
        if r.get("ok"):                          # the installer replaces the files and starts the new version
            # only the server stops: the window stays, says what is happening and reloads when the new version is up
            threading.Timer(1.5, lambda: ((getattr(app.state, "stop", None) or (lambda: None))(), hard_exit())).start()
        return r
    r = update.pull()
    if r.get("ok") and (r.get("changed") or _disk_version() != version.VERSION):
        threading.Timer(0.5, update.restart).start()
    return r


# ---------- V5: silent updates in the background ----------
# Found and downloaded by themselves; installed when no app window is open (tray only, e.g. after start with Windows)
# or when the user quits. An open window is never closed for an update.
def _window_open() -> bool:
    return time.time() - SEEN["t"] < 300          # a minimized window still polls about once a minute


def _update_on_quit():
    try:
        if winsetup.INSTALLED:
            v = selfupdate.ready(DATA / "updates")
            if v:
                log.info("installing %s on quit", v)
                selfupdate.run(DATA / "updates" / f"PDFactory-Setup-{v}.exe", DATA / "updates", relaunch="none")
        elif (APP_DIR / ".git").exists():
            r = update.check()
            if r.get("ok") and r.get("behind"):
                update.pull()                           # the next start runs the new code
    except Exception:
        log.exception("update on quit")


def _auto_update():
    time.sleep(90)
    last_check = 0.0
    while True:
        try:
            if time.time() - last_check > 3600:
                last_check = time.time()
                if winsetup.INSTALLED:
                    selfupdate.check()
                    selfupdate.download(DATA / "updates")       # quietly, once
                    pending = bool(selfupdate.ready(DATA / "updates"))
                else:
                    r = update_check()
                    pending = r.get("ok") and bool(r.get("behind") or r.get("restart"))
                _auto_update.pending = pending
            if getattr(_auto_update, "pending", False) and not _window_open():
                if winsetup.INSTALLED:
                    v = selfupdate.ready(DATA / "updates")
                    log.info("background update to %s", v)
                    selfupdate.run(DATA / "updates" / f"PDFactory-Setup-{v}.exe", DATA / "updates", relaunch="tiho")
                    time.sleep(1.5)
                    (getattr(app.state, "stop", None) or (lambda: None))()
                    hard_exit()
                r = update.pull()
                if r.get("ok"):
                    log.info("background update (git)")
                    update.restart("--tiho")
                    return
                _auto_update.pending = False
        except Exception:
            log.exception("background update")
        time.sleep(60)


if winsetup.WIN:
    threading.Thread(target=_auto_update, name="auto-update", daemon=True).start()


def hard_exit():
    """P11: os._exit skips atexit; hardexit runs it first (data/tmp, session copies, last log line)."""
    hardexit.exit()


def _stop(keep_window: bool):
    time.sleep(0.3)
    if keep_window:
        # restart after an update (V2/V5): only the server goes, the open window waits and reloads itself
        if app.state.stop:
            app.state.stop()
    else:
        _update_on_quit()
        if app.state.quit:
            app.state.quit()
    hard_exit()


@app.post("/api/shutdown")
def shutdown(body: dict = Body(default={})):
    keep = bool(body.get("keep_window"))
    log.info("shutdown from the app%s", " (restart, window stays)" if keep else "")
    threading.Thread(target=_stop, args=(keep,), daemon=True).start()
    return {"ok": True}


@app.post("/api/uninstall")
def uninstall():
    """Settings → Uninstall. Installed copy: the Inno uninstaller runs after this process exits; dev copy: Windows entries only."""
    mode = winsetup.uninstall()
    log.info("uninstall: %s", mode)
    shutdown()
    return {"ok": True, "mode": mode}


@app.post("/api/ugasi")
def ugasi():
    return shutdown()
