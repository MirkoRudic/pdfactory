"""PDF work: sources (open files), rendering, text, composing a workspace into a new PDF, OCR.

Coordinates exchanged with the UI are DISPLAY points: the page as it is shown, with its rotation
applied, 1 unit = 1 pt, origin top-left. They are converted to PDF space with page.derotation_matrix.
"""
import io
import math
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

import pymupdf as fitz

import applog
import fonts

log = applog.get("pdf")

SOURCES: dict[str, "Source"] = {}
IMAGES: dict[str, bytes] = {}
_lock = threading.RLock()


class UserError(Exception):
    """Short message for the user (L4); details go to the log."""


class Source:
    def __init__(self, data: bytes, path: str | None, name: str):
        self.id = uuid.uuid4().hex[:10]
        self.path = path
        self.name = name
        self.doc = fitz.open("pdf", data)
        if self.doc.needs_pass:
            raise UserError("PDF je zaključan lozinkom.")
        self.lock = threading.RLock()
        self.ocr = None  # progress dict while OCR runs

    def info(self):
        pages = []
        for p in self.doc:
            r = p.rect
            pages.append({"w": round(r.width, 2), "h": round(r.height, 2), "rot": p.rotation,
                          "forms": bool(p.first_widget)})
        return {"id": self.id, "name": self.name, "path": self.path, "pages": pages,
                "hasText": any(len(p.get_text("text").strip()) > 20 for p in self.doc)}


# ---------- opening ----------

def open_path(path: str) -> Source:
    p = Path(path)
    if not p.exists():
        raise UserError("Fajl ne postoji.")
    data = p.read_bytes()
    return _add(data, str(p), p.name)


def open_bytes(data: bytes, name: str) -> Source:
    return _add(data, None, name)


def _add(data: bytes, path, name) -> Source:
    ext = Path(name).suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"):
        data = image_to_pdf(data)
        name = Path(name).stem + ".pdf"
        path = None
    elif not data[:1024].lstrip().startswith(b"%PDF") and b"%PDF" not in data[:1024]:
        raise UserError("Ovo nije PDF fajl.")
    try:
        s = Source(data, path, name)
    except UserError:
        raise
    except Exception:
        log.exception("open failed: %s", name)
        raise UserError("PDF ne može da se otvori (oštećen fajl).")
    with _lock:
        SOURCES[s.id] = s
    log.info("open %s (%d pages) id=%s", path or name, s.doc.page_count, s.id)
    return s


def image_to_pdf(data: bytes) -> bytes:
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    im.load()
    if im.mode not in ("RGB", "L"):
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[3])
        im = bg
    dpi = im.info.get("dpi", (150, 150))[0] or 150
    w, h = im.width * 72 / dpi, im.height * 72 / dpi
    buf = io.BytesIO()
    im.save(buf, "PNG" if im.mode == "L" else "JPEG", quality=92)
    d = fitz.open()
    pg = d.new_page(width=w, height=h)
    pg.insert_image(pg.rect, stream=buf.getvalue())
    return d.tobytes()


def get(src_id: str) -> Source:
    s = SOURCES.get(src_id)
    if not s:
        raise UserError("Dokument više nije otvoren. Otvori ga ponovo.")
    return s


def close(src_id: str):
    with _lock:
        s = SOURCES.pop(src_id, None)
    if s:
        s.doc.close()


# ---------- rendering & text ----------

def render(src_id: str, page: int, width_px: int, extra_rot: int = 0, gray=False) -> bytes:
    s = get(src_id)
    with s.lock:
        p = s.doc[page]
        rot = (p.rotation + extra_rot) % 360
        rect = p.rect if extra_rot % 180 == 0 else fitz.Rect(0, 0, p.rect.height, p.rect.width)
        zoom = max(0.05, min(8.0, width_px / rect.width))
        m = fitz.Matrix(zoom, zoom).prerotate(extra_rot)
        pix = p.get_pixmap(matrix=m, alpha=False, colorspace=fitz.csGRAY if gray else fitz.csRGB)
        return pix.tobytes("png")


def page_text(src_id: str, page: int):
    """Words (for selection/search) and spans (for 'fix text'), in display coordinates."""
    s = get(src_id)
    with s.lock:
        p = s.doc[page]
        rm = p.rotation_matrix
        words = []
        for w in p.get_text("words", sort=True):
            r = fitz.Rect(w[:4]) * rm
            words.append([round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2), w[4]])
        spans, lines = [], []
        d = p.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for b in d["blocks"]:
            for line in b.get("lines", []):
                ls = [sp for sp in line["spans"] if sp["text"].strip()]
                if ls:   # "fix text" works on a whole line: PDFs often split a line into many spans (fonts, edits)
                    main = max(ls, key=lambda sp: len(sp["text"].strip()))
                    r = fitz.Rect()
                    for sp in ls:
                        r |= fitz.Rect(sp["bbox"])
                    r = r * rm
                    c = main["color"]
                    lines.append({"bbox": [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)],
                                  "text": "".join(sp["text"] for sp in line["spans"]).strip(),
                                  "size": round(main["size"], 1), "font": fonts.match(main["font"]), "pdfFont": main["font"],
                                  "bold": bool(main["flags"] & 16) or "bold" in main["font"].lower(),
                                  "italic": bool(main["flags"] & 2) or "italic" in main["font"].lower(),
                                  "color": "#%06x" % c})
                for sp in line["spans"]:
                    if not sp["text"].strip():
                        continue
                    r = fitz.Rect(sp["bbox"]) * rm
                    c = sp["color"]
                    spans.append({"bbox": [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)],
                                  "text": sp["text"], "size": round(sp["size"], 1),
                                  "font": fonts.match(sp["font"]), "pdfFont": sp["font"],
                                  "bold": bool(sp["flags"] & 16) or "bold" in sp["font"].lower(),
                                  "italic": bool(sp["flags"] & 2) or "italic" in sp["font"].lower(),
                                  "color": "#%06x" % c})
        return {"words": words, "spans": spans, "lines": lines}


def ocr_rect(src_id: str, page: int, rect, lang: str, tessdata: str) -> str:
    """What the text in a rectangle LOOKS like (OCR of the rendered page). Used for 'fix text': many PDFs map
    their glyphs to wrong letters (č shown, 'c' extracted; 'ž' -> 'f'), so the extracted text can't be trusted."""
    s = get(src_id)
    with s.lock:
        p = s.doc[page]
        r = fitz.Rect(rect) * p.derotation_matrix
        r.normalize()
        r = (r + (-2, -2, 2, 2)) & p.rect
        pix = p.get_pixmap(dpi=300, clip=r)
    # a margin around the line helps Tesseract
    from PIL import Image
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    big = Image.new("RGB", (pix.width + 80, pix.height + 80), "white")
    big.paste(im, (40, 40))
    buf = io.BytesIO()
    big.save(buf, "PNG")
    pm = fitz.Pixmap(buf.getvalue())
    pm.set_dpi(300, 300)
    d = fitz.open("pdf", pm.pdfocr_tobytes(language=lang, tessdata=tessdata))
    return " ".join(d[0].get_text("text").split())


def page_forms(src_id: str, page: int):
    s = get(src_id)
    out = []
    with s.lock:
        p = s.doc[page]
        rm = p.rotation_matrix
        for w in p.widgets() or []:
            r = w.rect * rm
            out.append({"name": w.field_name, "type": w.field_type_string, "value": w.field_value,
                        "options": w.choice_values or [], "on": w.on_state() if w.field_type in (2, 5) else None,
                        "rect": [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]})
    return out


def search(src_id: str, q: str):
    s = get(src_id)
    hits = []
    with s.lock:
        for i, p in enumerate(s.doc):
            rm = p.rotation_matrix
            for r in p.search_for(q, quads=False):
                r = r * rm
                hits.append({"page": i, "rect": [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]})
            if len(hits) > 2000:
                break
    return hits


# ---------- composing a workspace ----------

def _rgb(hexcol, default=(0, 0, 0)):
    if not hexcol:
        return None
    try:
        h = hexcol.lstrip("#")
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except (ValueError, AttributeError):
        return default


def _to_pdf(page, rect):
    r = fitz.Rect(rect) * page.derotation_matrix
    r.normalize()
    return r


def compose(items: list[dict], objects: dict | None = None, forms: dict | None = None) -> fitz.Document:
    """items: [{src, page, rot, uid}] -> new document with edits applied.
    objects: {uid: [object, ...]} in display coordinates of that item. forms: {uid: {field: value}}."""
    if not items:
        raise UserError("Nema nijedne strane.")
    objects, forms = objects or {}, forms or {}
    first = items[0]["src"]
    identity = (all(it["src"] == first and it["page"] == i and not it.get("rot") for i, it in enumerate(items))
                and len(items) == get(first).doc.page_count)
    if identity:
        s = get(first)
        with s.lock:
            out = fitz.open("pdf", s.doc.tobytes())
    else:
        out = fitz.open()
        for it in items:
            s = get(it["src"])
            with s.lock:
                out.insert_pdf(s.doc, from_page=it["page"], to_page=it["page"], annots=True, widgets=True)
            p = out[-1]
            if it.get("rot"):
                p.set_rotation((p.rotation + it["rot"]) % 360)
    # forms first (widgets live in PDF space and are not affected by redactions below)
    for i, it in enumerate(items):
        vals = forms.get(it.get("uid", ""))
        if vals:
            _apply_forms(out[i], vals)
    every = [o for objs in objects.values() for o in objs if o.get("type") == "image" and o.get("allPages")]
    for i, it in enumerate(items):
        objs = [o for o in objects.get(it.get("uid", ""), []) if not (o.get("type") == "image" and o.get("allPages"))]
        _apply_objects(out[i], objs + every)
    return out


def _apply_forms(page, vals: dict):
    for w in page.widgets() or []:
        if w.field_name in vals:
            v = vals[w.field_name]
            try:
                if w.field_type in (2, 5):  # checkbox, radio
                    w.field_value = w.on_state() if v else "Off"
                else:
                    w.field_value = str(v)
                w.update()
            except Exception:
                log.exception("form field %s", w.field_name)


def _apply_objects(page, objs: list[dict]):
    # 1. text corrections: remove the old text first (only text, images and lines stay)
    fixes = [o for o in objs if o.get("type") == "fix"]
    for o in fixes:
        x0, y0, x1, y1 = o["orig"]
        inset = (y1 - y0) * 0.18      # line boxes overlap the lines above/below; don't take their letters
        page.add_redact_annot(_to_pdf(page, (x0, y0 + inset, x1, y1 - inset)), fill=False)
    if fixes:
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
    # 2. everything in drawing order
    for o in objs:
        t = o.get("type")
        try:
            if t in ("text", "fix"):
                _text(page, o)
            elif t == "image":
                _image(page, o)
            elif t == "shape":
                _shape(page, o)
            elif t == "mark":
                _mark(page, o)
        except UserError:
            raise
        except Exception:
            log.exception("object %s failed on page %s", t, page.number)
            raise UserError("Jedna izmena ne može da se upiše u PDF. Detalji su u dnevniku.")


def _css_font(o) -> tuple[str, fitz.Archive]:
    fam = o.get("font") or fonts.default_family()
    arch = fitz.Archive()
    faces, dirs = [], set()
    for key, weight, style in (("r", "normal", "normal"), ("b", "bold", "normal"),
                               ("i", "normal", "italic"), ("bi", "bold", "italic")):
        f = fonts.file_for(fam, key)
        if not f:
            continue
        d = str(Path(f).parent)
        if d not in dirs:
            arch.add(d)
            dirs.add(d)
        faces.append(f'@font-face{{font-family:"F";font-weight:{weight};font-style:{style};src:url("{Path(f).name}");}}')
    return "".join(faces), arch


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _text(page, o):
    text = o.get("text", "")
    if not text.strip():
        return
    faces, arch = _css_font(o)
    deco = " ".join(x for x, on in (("underline", o.get("underline")), ("line-through", o.get("strike"))) if on) or "none"
    css = (faces + "body{margin:0;padding:0}"
           f'p{{margin:0;padding:0;font-family:"F",sans-serif;font-size:{float(o.get("size", 12))}px;'
           f'line-height:{float(o.get("lineHeight", 1.2))};color:{o.get("color", "#000000")};'
           f'font-weight:{"bold" if o.get("bold") else "normal"};font-style:{"italic" if o.get("italic") else "normal"};'
           f'text-decoration:{deco};text-align:{o.get("align", "left")};white-space:pre-wrap;}}')
    html = "".join(f"<p>{_esc(line) or '&#160;'}</p>" for line in text.split("\n"))
    x, y, w, h = o["x"], o["y"], o["w"], o["h"]
    if o.get("type") == "fix":
        # a corrected line stays one line: as wide as the new text needs (measured with the real font)
        css = css.replace("white-space:pre-wrap", "white-space:pre")
        f = fonts.file_for(o.get("font") or fonts.default_family(), "bi" if o.get("bold") and o.get("italic")
                           else "b" if o.get("bold") else "i" if o.get("italic") else "r")
        try:
            need = max(fitz.Font(fontfile=f).text_length(line, float(o.get("size", 12))) for line in text.split("\n"))
            w = max(w, need * 1.04 + 2)
        except Exception:
            log.exception("text width")
    disp_h = page.rect.height if page.rotation % 180 == 0 else page.rect.width
    bottom = disp_h
    for grow in (1.0, 1.15, 1.4, 2.0, None):
        hh = (bottom - y) if grow is None else h * grow
        rect = _to_pdf(page, (x, y, x + w * (1.02 if grow else 1), y + hh))
        spare, _ = page.insert_htmlbox(rect, html, css=css, archive=arch, rotate=page.rotation,
                                       scale_low=1 if grow else 0)
        if spare >= 0:
            return


def _image(page, o):
    from PIL import Image
    data = IMAGES.get(o.get("img", ""))
    if data is None:
        raise UserError("Slika više nije dostupna. Ubaci je ponovo.")
    im = Image.open(io.BytesIO(data))
    im.load()
    im = im.convert("RGBA")
    c = o.get("crop") or {}
    if any(c.get(k) for k in ("l", "t", "r", "b")):
        W, H = im.size
        box = (int(W * c.get("l", 0)), int(H * c.get("t", 0)), int(W * (1 - c.get("r", 0))), int(H * (1 - c.get("b", 0))))
        if box[2] > box[0] and box[3] > box[1]:
            im = im.crop(box)
    if o.get("flipH"):
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    if o.get("flipV"):
        im = im.transpose(Image.FLIP_TOP_BOTTOM)
    x, y, w, h = o["x"], o["y"], o["w"], o["h"]
    ang = float(o.get("angle", 0)) % 360
    cx, cy = x + w / 2, y + h / 2
    if ang:
        im = im.rotate(-ang, expand=True, resample=Image.BICUBIC)
        a = math.radians(ang)
        bw = abs(w * math.cos(a)) + abs(h * math.sin(a))
        bh = abs(w * math.sin(a)) + abs(h * math.cos(a))
        x, y, w, h = cx - bw / 2, cy - bh / 2, bw, bh
    op = float(o.get("opacity", 1))
    if op < 1:
        alpha = im.split()[3].point(lambda v: int(v * op))
        im.putalpha(alpha)
    buf = io.BytesIO()
    if im.getextrema()[3][0] == 255:  # fully opaque: JPEG keeps files small for photos
        im.convert("RGB").save(buf, "JPEG", quality=90)
    else:
        im.save(buf, "PNG", optimize=True)
    page.insert_image(_to_pdf(page, (x, y, x + w, y + h)), stream=buf.getvalue(), keep_proportion=False,
                      rotate=page.rotation, overlay=not o.get("behind"))


def _shape(page, o):
    kind = o.get("kind", "rect")
    x, y, w, h = o["x"], o["y"], o["w"], o["h"]
    dm = page.derotation_matrix
    sh = page.new_shape()
    stroke = _rgb(o.get("stroke"))
    fill = _rgb(o.get("fill")) if kind in ("rect", "ellipse") else None
    width = float(o.get("width", 2))
    if kind == "rect":
        sh.draw_rect(_to_pdf(page, (x, y, x + w, y + h)))
    elif kind == "ellipse":
        sh.draw_oval(_to_pdf(page, (x, y, x + w, y + h)))
    else:
        p1, p2 = fitz.Point(x, y), fitz.Point(x + w, y + h)
        sh.draw_line(p1 * dm, p2 * dm)
        if kind == "arrow":
            ang = math.atan2(p2.y - p1.y, p2.x - p1.x)
            ln = max(9, width * 4)
            for d in (0.45, -0.45):
                q = fitz.Point(p2.x - ln * math.cos(ang + d), p2.y - ln * math.sin(ang + d))
                sh.draw_line(p2 * dm, q * dm)
    op = float(o.get("opacity", 1))
    sh.finish(color=stroke, fill=fill, width=width if stroke else 0, stroke_opacity=op, fill_opacity=op,
              lineCap=1, lineJoin=1, closePath=kind in ("rect", "ellipse"))
    sh.commit(overlay=True)


def _mark(page, o):
    """Highlighter: translucent band over the text."""
    x, y, w, h = o["x"], o["y"], o["w"], o["h"]
    sh = page.new_shape()
    sh.draw_rect(_to_pdf(page, (x, y, x + w, y + h)))
    sh.finish(color=None, fill=_rgb(o.get("color", "#ffd600")), fill_opacity=float(o.get("opacity", 0.4)), width=0)
    sh.commit(overlay=True)


# ---------- saving ----------

def save_doc(doc: fitz.Document, target: str, backup_dir: Path | None = None, keep=20):
    t = Path(target)
    if t.suffix.lower() != ".pdf":
        t = t.with_suffix(".pdf")
    if backup_dir and t.exists():
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(t, backup_dir / f"{time.strftime('%Y-%m-%d_%H%M%S')}_{t.name}")
        olds = sorted(backup_dir.glob("*.pdf"))
        for old in olds[:-keep]:
            try:
                old.unlink()
            except OSError:
                pass
    tmp = t.with_name(t.name + ".pfsave")
    try:
        doc.save(str(tmp), garbage=3, deflate=True)
        os.replace(tmp, t)
    except PermissionError:
        tmp.unlink(missing_ok=True)
        raise UserError("Fajl je otvoren u drugom programu ili je zaključan. Zatvori ga pa probaj ponovo.")
    except OSError:
        tmp.unlink(missing_ok=True)
        log.exception("save failed %s", t)
        raise UserError("Čuvanje nije uspelo. Detalji su u dnevniku.")
    log.info("saved %s (%d pages, %d KB)", t, doc.page_count, t.stat().st_size // 1024)
    return str(t)


def parse_ranges(text: str, n: int) -> list[int]:
    """'sve' / '' -> all; '1-3, 5, 8-' -> 0-based page list."""
    t = (text or "").strip().lower()
    if t in ("", "sve", "sva", "all"):
        return list(range(n))
    out = []
    for part in re.split(r"[,;\s]+", t):
        if not part:
            continue
        m = re.fullmatch(r"(\d*)\s*-\s*(\d*)", part)
        if m:
            a = int(m.group(1) or 1)
            b = int(m.group(2) or n)
            out += list(range(max(1, a), min(n, b) + 1))
        elif part.isdigit() and 1 <= int(part) <= n:
            out.append(int(part))
        else:
            raise UserError(f"Ne razumem „{part}“ u spisku strana.")
    return [p - 1 for p in out]


def n_up(doc: fitz.Document, per_sheet: int) -> fitz.Document:
    if per_sheet <= 1:
        return doc
    out = fitz.open()
    W, H = fitz.paper_size("a4-l")
    for i in range(0, doc.page_count, 2):
        sheet = out.new_page(width=W, height=H)
        for k in range(2):
            if i + k < doc.page_count:
                cell = fitz.Rect(k * W / 2 + 12, 12, (k + 1) * W / 2 - 12, H - 12)
                sheet.show_pdf_page(cell, doc, i + k, keep_proportion=True)
    return out


# ---------- OCR ----------

def find_tessdata(configured: str = "") -> str | None:
    """Folder with *.traineddata. PyMuPDF has Tesseract built in and only needs the language files."""
    cands = [configured, str(Path(__file__).resolve().parents[1] / "tessdata"), os.environ.get("TESSDATA_PREFIX", "")]
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", ""),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        if base:
            cands.append(os.path.join(base, "Tesseract-OCR", "tessdata"))
    cands += ["/usr/share/tesseract-ocr/5/tessdata", "/usr/share/tesseract-ocr/4.00/tessdata", "/usr/share/tessdata"]
    exe = shutil.which("tesseract")
    if exe:
        cands.append(str(Path(exe).resolve().parent / "tessdata"))
    for c in cands:
        if c and Path(c).is_dir() and any(Path(c).glob("*.traineddata")):
            return str(Path(c))
    # other VAJB apps may carry their own copy (searched two levels deep)
    vajb = Path(__file__).resolve().parents[2]
    for p in list(vajb.glob("*/tessdata")) + list(vajb.glob("*/*/tessdata")) + list(vajb.glob("*/*/*/tessdata")):
        if any(p.glob("*.traineddata")):
            return str(p)
    return None


def tess_langs(tessdata: str | None) -> list[str]:
    if not tessdata:
        return []
    return sorted(p.stem for p in Path(tessdata).glob("*.traineddata") if p.stem != "osd")


def ocr_source(src_id: str, lang: str, tessdata: str, fontfile: str | None):
    """Adds an invisible text layer to pages without text. Runs in a thread; progress in s.ocr."""
    s = get(src_id)
    s.ocr = {"done": 0, "total": s.doc.page_count, "state": "radi", "added": 0}
    t0 = last = time.time()
    try:
        with s.lock:
            for i, p in enumerate(s.doc):
                if len(p.get_text("text").strip()) < 20:
                    pix = p.get_pixmap(dpi=300)  # grayscale pixmaps give no text (measured)
                    ocr = fitz.open("pdf", pix.pdfocr_tobytes(language=lang, tessdata=tessdata))
                    op = ocr[0]
                    sx, sy = p.rect.width / op.rect.width, p.rect.height / op.rect.height
                    rm_inv = p.derotation_matrix
                    for w in op.get_text("words"):
                        r = fitz.Rect(w[0] * sx, w[1] * sy, w[2] * sx, w[3] * sy)  # display space
                        txt = w[4] + " "
                        fs = max(3.0, r.height * 0.82)
                        # baseline-left corner of the word in display space -> PDF space
                        pt = fitz.Point(r.x0, r.y1 - r.height * 0.18) * rm_inv
                        kw = {"fontfile": fontfile, "fontname": "ocrf"} if fontfile else {"fontname": "helv"}
                        try:
                            tl = fitz.get_text_length(txt, fontname="helv", fontsize=fs)
                            morph = None
                            if tl > 0:
                                k = r.width / tl
                                morph = (pt, fitz.Matrix(k, 1)) if 0.2 < k < 5 else None
                            p.insert_text(pt, txt, fontsize=fs, render_mode=3, rotate=p.rotation, morph=morph, **kw)
                        except Exception:
                            p.insert_text(pt, txt, fontsize=fs, render_mode=3, rotate=p.rotation, **kw)
                    s.ocr["added"] += 1
                s.ocr["done"] = i + 1
                if time.time() - last > 60:
                    log.info("ocr %s: %d/%d", s.name, i + 1, s.doc.page_count)
                    last = time.time()
        s.ocr["state"] = "gotovo"
        log.info("ocr %s done: %d pages got text (%d s)", s.name, s.ocr["added"], int(time.time() - t0))
    except Exception:
        log.exception("ocr failed %s", s.name)
        s.ocr["state"] = "greška"
