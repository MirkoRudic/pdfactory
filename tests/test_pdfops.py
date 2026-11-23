"""Core tests without a browser: python tests/test_pdfops.py"""
import io, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import applog
W = Path(tempfile.mkdtemp(dir=ROOT / "data")) if (ROOT / "data").exists() else Path(tempfile.mkdtemp())
applog.setup(W / "logs", "test")
import fonts, pdfops as P
import subprocess
subprocess.run([sys.executable, str(ROOT / "tests" / "make_samples.py"), str(W)], check=True)
fonts.init(W / "fonts.json")
s = P.open_path(str(W / "ugovor.pdf"))
assert s.doc.page_count == 3
sp = P.page_text(s.id, 0)["spans"][1]
from PIL import Image
b = io.BytesIO(); Image.new("RGB", (40, 20), "red").save(b, "PNG"); P.IMAGES["i"] = b.getvalue()
items = [{"src": s.id, "page": i, "uid": f"u{i}"} for i in range(3)]
objs = {"u0": [{"type": "fix", "orig": sp["bbox"], "x": sp["bbox"][0], "y": sp["bbox"][1], "w": 300, "h": 18, "text": "Iznos: 999 RSD", "size": 12},
               {"type": "text", "x": 72, "y": 300, "w": 200, "h": 30, "text": "Ćao ЉЊ", "size": 14},
               {"type": "image", "img": "i", "x": 72, "y": 400, "w": 80, "h": 40, "angle": 45, "opacity": 0.5},
               {"type": "shape", "kind": "arrow", "x": 10, "y": 10, "w": 50, "h": 50, "stroke": "#000000", "width": 2}],
        "u2": [{"type": "text", "x": 30, "y": 30, "w": 200, "h": 20, "text": "rotirana", "size": 12}]}
d = P.compose(items, objs, {"u0": {"ime": "Test"}})
out = P.save_doc(d, str(W / "out.pdf"))
r = P.open_path(out)
t0 = r.doc[0].get_text()
assert "999 RSD" in t0 and "100.000" not in t0 and "Ćao" in t0, t0
assert "rotirana" in r.doc[2].get_text()
assert [w.field_value for w in r.doc[0].widgets()][0] == "Test"
assert P.parse_ranges("1-2,3", 5) == [0, 1, 2] and P.parse_ranges("", 2) == [0, 1]
sk = P.open_path(str(W / "skenirano.pdf"))
td = P.find_tessdata()
if td:
    lang = "eng" if "eng" in P.tess_langs(td) else P.tess_langs(td)[0]
    P.ocr_source(sk.id, lang, td, fonts.file_for(fonts.default_family()))
    assert "snimanje" in sk.doc[0].get_text(), sk.doc[0].get_text()
print("OK", W)
import shutil
if W.parent == ROOT / "data":
    shutil.rmtree(W, ignore_errors=True)
