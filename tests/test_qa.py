"""Regressions found by the QA pass of 27.11.2026: python tests/test_qa.py"""
import sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import applog
W = Path(tempfile.mkdtemp())
applog.setup(W / "logs", "test")
import pymupdf as fitz
import pdfops as P

fails = []
def check(name, ok, info=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  {info}"))
    if not ok:
        fails.append(name)

# 1. deleting / rotating a page keeps the outline, metadata and internal links
d = fitz.open()
for i in range(3):
    d.new_page().insert_text((72, 90), f"Strana {i+1}")
d.set_toc([[1, "One", 1], [1, "Two", 2], [1, "Three", 3]])
d.set_metadata({"title": "Naslov"})
d[0].insert_link({"kind": fitz.LINK_GOTO, "from": fitz.Rect(72, 100, 200, 120), "page": 2})
d.save(W / "toc.pdf")
s = P.open_path(str(W / "toc.pdf"))
out = P.compose([{"src": s.id, "page": 0, "uid": "a"}, {"src": s.id, "page": 2, "uid": "c"}])
check("delete keeps outline", [t[1] for t in out.get_toc()] == ["One", "Three"], out.get_toc())
check("delete keeps metadata", out.metadata.get("title") == "Naslov", out.metadata)
check("delete keeps internal link", any(l.get("page") == 1 for l in out[0].get_links()), out[0].get_links())
out = P.compose([{"src": s.id, "page": i, "uid": str(i), "rot": 90 if i == 1 else 0} for i in range(3)])
check("rotate keeps outline", len(out.get_toc()) == 3 and out[1].rotation == 90, (out.get_toc(), out[1].rotation))

# 2. merged forms with the same field name keep both values
for n in "ab":
    f = fitz.open(); p = f.new_page()
    w = fitz.Widget(); w.field_name = "Text1"; w.field_type = fitz.PDF_WIDGET_TYPE_TEXT; w.rect = fitz.Rect(72, 72, 300, 94)
    p.add_widget(w); f.save(W / f"form_{n}.pdf")
fa, fb = P.open_path(str(W / "form_a.pdf")), P.open_path(str(W / "form_b.pdf"))
out = P.compose([{"src": fa.id, "page": 0, "uid": "a"}, {"src": fb.id, "page": 0, "uid": "b"}],
                forms={"a": {"Text1": "AAA"}, "b": {"Text1": "BBB"}})
vals = [w.field_value for p in out for w in p.widgets()]
check("merged forms keep both values", vals == ["AAA", "BBB"], vals)

# 3. radio group: only the chosen option is on
f = fitz.open(); p = f.new_page()
for i, st in enumerate(["A", "B"]):
    w = fitz.Widget(); w.field_name = "grp"; w.field_type = fitz.PDF_WIDGET_TYPE_RADIOBUTTON
    w.rect = fitz.Rect(72, 72 + 30 * i, 88, 88 + 30 * i); w.button_caption = st; w.field_value = False
    p.add_widget(w)
for w, st in zip(p.widgets(), "AB"):  # distinct on-states, as in real radio groups
    f.xref_set_key(w.xref, "AP/N", f.xref_get_key(w.xref, "AP/N")[1].replace("/Yes", "/" + st))
f.save(W / "radio.pdf")
rs = P.open_path(str(W / "radio.pdf"))
on = [w.on_state() for w in rs.doc[0].widgets()]
out = P.compose([{"src": rs.id, "page": 0, "uid": "r"}], forms={"r": {"grp": on[1]}})
out.save(W / "radio_out.pdf"); r2 = fitz.open(W / "radio_out.pdf")
st = [r2.xref_get_key(w.xref, "AS")[1] for w in r2[0].widgets()]
check("radio keeps one choice", st == ["/Off", "/B"], (on, st))

# 4. OCR: a page that already has an OCR text layer is not recognized again
sc = fitz.open(); sp = sc.new_page(); sp.insert_text((72, 120), "Page 5", fontsize=40)
pix = sp.get_pixmap(dpi=150); img = fitz.open(); ip = img.new_page(width=sp.rect.width, height=sp.rect.height)
ip.insert_image(ip.rect, pixmap=pix); img.save(W / "scan.pdf")
td = P.find_tessdata()
if td:
    lang = "eng" if "eng" in P.tess_langs(td) else P.tess_langs(td)[0]
    cur = str(W / "scan.pdf")
    for k in range(2):
        so = P.open_path(cur)
        P.ocr_source(so.id, lang, td, None)
        cur = P.save_doc(P.compose([{"src": so.id, "page": 0, "uid": "x"}]), str(W / f"scan{k}.pdf"))
    txt = fitz.open(cur)[0].get_text()
    check("OCR layer added once", txt.count("Page") == 1, repr(txt))
    check("scan with OCR layer no longer needsOcr", not P.open_path(cur).info()["needsOcr"])

    # 5. OCR word boxes on a /Rotate 90 scan have the width of the word on screen
    def box(src):
        for w in src.doc[0].get_text("words"):
            if "Page" in w[4]:
                return fitz.Rect(w[:4]) * src.doc[0].rotation_matrix
    a = P.open_path(str(W / "scan.pdf")); P.ocr_source(a.id, lang, td, None); ra = box(a); rb = None
    for irot in (90, 270):  # whichever stores the image so that the page shows it upright
        rot = fitz.open(); rp = rot.new_page(width=sp.rect.height, height=sp.rect.width)
        rp.insert_image(rp.rect, pixmap=pix, rotate=irot); rp.set_rotation(90); rot.save(W / f"scan_rot{irot}.pdf")
        b = P.open_path(str(W / f"scan_rot{irot}.pdf")); P.ocr_source(b.id, lang, td, None)
        rb = box(b) or rb
    print("   boxes", ra, rb)
    check("OCR box on rotated scan", ra and rb and abs(ra.width - rb.width) < 0.02 * ra.width and abs(ra.height - rb.height) < 0.02 * ra.height, (ra, rb))
else:
    print("skip OCR (no tessdata)")

# 6. a scan with a short printed header (fax line, page number) is still recognized
hd = fitz.open(); hp = hd.new_page(); hp.insert_image(hp.rect, pixmap=pix); hp.insert_text((20, 20), "Fax 12", fontsize=8)
hd.save(W / "scan_header.pdf")
check("scan with a printed header needsOcr", P.open_path(str(W / "scan_header.pdf")).info()["needsOcr"])

# 7. "vertical" in page_text: only lines that run top-to-bottom on screen (short labels stay editable)
v = fitz.open()
for rot in (0, 90):
    vp = v.new_page(); vp.insert_text((72, 90), "1.", fontsize=12); vp.insert_text((72, 120), "Iznos: 100.000 RSD", fontsize=12)
    vp.set_rotation(rot)
v.save(W / "vert.pdf"); vs = P.open_path(str(W / "vert.pdf"))
l0 = [l["vertical"] for l in P.page_text(vs.id, 0)["lines"]]; l1 = [l["vertical"] for l in P.page_text(vs.id, 1)["lines"]]
check("short horizontal label is not vertical", l0 == [False, False], l0)
check("line on /Rotate 90 page is vertical", l1 == [True, True], l1)

# PowerShell single-quoted strings end at ' and at the typographic quotes too (folder "Mirko’s files")
import winsetup
q = winsetup._psq("C:\\Mirko’s ‘new’ it's\\a.lnk")
check("PowerShell quotes doubled", q == "C:\\Mirko’’s ‘‘new’’ it''s\\a.lnk", q)

# --instaliraj does not open the Windows default-apps page without context; the app asks in its dialog
pyw = (ROOT / "PDFactory.pyw").read_text(encoding="utf-8")
blk = pyw[pyw.index('if "--instaliraj" in flags:'):]
blk = blk[:blk.index('if "--uninstall"')]
check("install asks inside the app", "ask_default" in blk and "open_default_apps" not in pyw.split("def main")[1].split('if "--default"')[0])

print("FAILS:", fails if fails else "none")
sys.exit(1 if fails else 0)
