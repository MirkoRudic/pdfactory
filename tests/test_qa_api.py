"""QA 27.11.2026, server side: python tests/test_qa_api.py"""
import shutil, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
W = Path(tempfile.mkdtemp())
from fastapi.testclient import TestClient
import main, winsetup, pdfops
import pymupdf as fitz
c = TestClient(main.app, base_url="http://127.0.0.1")
fails = []
def check(name, ok, info=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  {info}"))
    if not ok:
        fails.append(name)

# 1. theme only takes known values (it goes into index.html unescaped)
before = c.get("/api/settings").json().get("theme")
c.post("/api/settings", json={"theme": 'dark"><script>alert(1)</script>'})
check("theme rejects markup", "<script>alert(1)" not in c.get("/").text)
c.post("/api/settings", json={"theme": before or "dark"})

# 2. split: an existing <name>_1.pdf is backed up before it is replaced
d = fitz.open()
for i in range(2):
    d.new_page().insert_text((72, 72), f"Nova {i+1}")
d.save(W / "dok.pdf")
old = fitz.open(); old.new_page().insert_text((72, 72), "STARI FAJL"); old.save(W / "dok_1.pdf")
s = pdfops.open_path(str(W / "dok.pdf"))
winsetup.ask_folder = lambda initial: str(W)
rez = main.DATA / "rezerva"
had = set(rez.glob("*")) if rez.exists() else set()
c.post("/api/split", json={"name": "dok.pdf", "parts": [[{"src": s.id, "page": 0, "uid": "a"}], [{"src": s.id, "page": 1, "uid": "b"}]]})
new = [p for p in (rez.glob("*") if rez.exists() else []) if p not in had]
check("split backs up a replaced file", any("STARI FAJL" in fitz.open(p)[0].get_text() for p in new), new)
for p in new:
    p.unlink()

# 3. only the marker in data/tmp is deleted, not a user's file of the same name
src = (ROOT / "PDFactory.pyw").read_text(encoding="utf-8")
check("marker check uses data/tmp", 'Path(path).parent == (DATA / "tmp").resolve()' in src)

# 4. restart after an update keeps the window (V2/V5): only the server stops
import types
calls = []
real_os, real_sleep, real_uoq = main.os, main.time.sleep, main._update_on_quit
main.os = types.SimpleNamespace(_exit=lambda c: calls.append("exit"))
main.time.sleep = lambda s: None
main._update_on_quit = lambda: calls.append("update_on_quit")
main.app.state.stop = lambda: calls.append("stop")
main.app.state.quit = lambda: calls.append("quit")
try:
    main._stop(True)
    check("restart stops only the server", calls == ["stop", "exit"], calls)
    calls.clear(); main._stop(False)
    check("quit closes everything", calls == ["update_on_quit", "quit", "exit"], calls)
finally:
    main.os, main.time.sleep, main._update_on_quit = real_os, real_sleep, real_uoq
    main.app.state.stop = main.app.state.quit = None
check("launcher keeps the window on --restart", '"--restart" in flags) and app_windows()' in (ROOT / "PDFactory.pyw").read_text(encoding="utf-8"))

# 5. inbox tells the window which server it talks to (a restart it did not ask for -> reload)
check("inbox has the server pid", c.get("/api/inbox").json().get("pid") == main.os.getpid())

# 6. a restarted server still knows dropped files and inserted images by their ids (unsaved work survives)
import io
from PIL import Image
up = c.post("/api/upload", files={"file": ("bez_putanje.pdf", (W / "dok.pdf").read_bytes(), "application/pdf")}).json()
buf = io.BytesIO(); Image.new("RGB", (40, 20), "red").save(buf, "PNG")
iid = c.post("/api/image", files={"file": ("logo.png", buf.getvalue(), "image/png")}).json()["id"]
pdfops.SOURCES.clear(); pdfops.IMAGES.clear()          # what a restart does to memory
check("dropped file known after restart", c.get(f"/api/src/{up['id']}").status_code == 200)
check("image known after restart", c.get(f"/api/image/{iid}").status_code == 200)
doc = pdfops.compose([{"src": up["id"], "page": 0, "uid": "u"}],
                     {"u": [{"type": "image", "img": iid, "x": 10, "y": 10, "w": 40, "h": 20, "angle": 0, "opacity": 1}]}, {})
check("image is in the saved file after restart", len(doc[0].get_images()) == 1)
c.post(f"/api/close/{up['id']}", json={})
check("closing removes the session copy", not (main.DATA / "session" / f"{up['id']}.pdf").exists())
check("unknown id is not read from disk", c.get("/api/src/..%2f..%2fx").status_code != 200)

# 6b. session copies: a .pdf without its .json is dropped at start, a closed id is never reloaded,
#     an open source is marked as used before the server stops (QA light pass 27.11.2026)
import os, time as _t
ses = main.DATA / "session"
s2 = pdfops.open_path(str(W / "dok.pdf"))
old = _t.time() - 10 * 86400
for n in (f"{s2.id}.pdf", f"{s2.id}.json"):
    os.utime(ses / n, (old, old))
pdfops.touch_session()
check("open source touched before stop", (ses / f"{s2.id}.json").stat().st_mtime > old + 86400)
os.utime(ses / f"{s2.id}.json", (old, old)); os.utime(ses / f"{s2.id}.pdf", (_t.time(), _t.time()))
pdfops.init_session(ses)
check("pdf and json pruned together", (ses / f"{s2.id}.json").exists())
(ses / "abcdef0123.pdf").write_bytes(b"%PDF")
pdfops.init_session(ses)
check("orphan pdf dropped", not (ses / "abcdef0123.pdf").exists())
pdfops.close(s2.id)
_keep_before = pdfops._keep
pdfops._keep(f"{s2.id}.pdf", (W / "dok.pdf").read_bytes()); pdfops._keep(f"{s2.id}.json", b"{}")
check("closed id is not reloaded", c.get(f"/api/src/{s2.id}").status_code != 200)
pdfops._drop(f"{s2.id}.pdf"); pdfops._drop(f"{s2.id}.json")

# 7. leaving through os._exit still empties data/tmp (atexit does not run there)
left = main.DATA / "tmp" / "left_behind.txt"; left.write_text("x")
real_os = main.os
main.os = types.SimpleNamespace(_exit=lambda c: None, getpid=real_os.getpid)
try:
    main.hard_exit()
finally:
    main.os = real_os
check("exit empties data/tmp", not left.exists())

shutil.rmtree(W, ignore_errors=True)
print("FAILS:", fails if fails else "none")
sys.exit(1 if fails else 0)
