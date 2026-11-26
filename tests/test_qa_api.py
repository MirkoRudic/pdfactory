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

shutil.rmtree(W, ignore_errors=True)
print("FAILS:", fails if fails else "none")
sys.exit(1 if fails else 0)
