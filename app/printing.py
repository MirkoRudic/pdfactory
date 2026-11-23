"""Printing on Windows through GDI (pywin32). The app shows its own print window (UI4);
Windows print dialogs are never opened."""
import io
import sys
import threading

import pymupdf as fitz

import applog

log = applog.get("print")
JOBS: dict[str, dict] = {}


def available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import win32print  # noqa: F401
        return True
    except ImportError:
        return False


def printers() -> dict:
    if not available():
        return {"printers": [], "default": None}
    import win32print
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    names = [p[2] for p in win32print.EnumPrinters(flags)]
    try:
        default = win32print.GetDefaultPrinter()
    except Exception:
        default = names[0] if names else None
    return {"printers": names, "default": default}


def start(job_id: str, doc: fitz.Document, opts: dict):
    JOBS[job_id] = {"state": "radi", "done": 0, "total": doc.page_count, "error": None}
    threading.Thread(target=_run, args=(job_id, doc, opts), name="stampa", daemon=True).start()


def _run(job_id, doc, o):
    j = JOBS[job_id]
    try:
        import win32con
        import win32gui
        import win32print
        import win32ui
        from PIL import Image, ImageWin
        name = o["printer"]
        h = win32print.OpenPrinter(name)
        try:
            dm = win32print.GetPrinter(h, 2)["pDevMode"]
        finally:
            win32print.ClosePrinter(h)
        if dm is not None:
            dm.Copies = 1
            dm.Color = 1 if o.get("gray") else 2                  # DMCOLOR_MONOCHROME / COLOR
            dm.Duplex = 2 if o.get("duplex") else 1               # DMDUP_VERTICAL (long edge) / SIMPLEX
            dm.Fields |= win32con.DM_COLOR | win32con.DM_DUPLEX | win32con.DM_COPIES
        hdc_raw = win32gui.CreateDC("WINSPOOL", name, dm)
        dc = win32ui.CreateDCFromHandle(hdc_raw)
        pw, ph = dc.GetDeviceCaps(win32con.HORZRES), dc.GetDeviceCaps(win32con.VERTRES)
        dpix, dpiy = dc.GetDeviceCaps(win32con.LOGPIXELSX), dc.GetDeviceCaps(win32con.LOGPIXELSY)
        offx, offy = dc.GetDeviceCaps(win32con.PHYSICALOFFSETX), dc.GetDeviceCaps(win32con.PHYSICALOFFSETY)
        copies = max(1, int(o.get("copies", 1)))
        j["total"] = doc.page_count * copies
        dc.StartDoc(o.get("title", "PDFabrika"))
        for _ in range(copies):
            for page in doc:
                landscape_page = page.rect.width > page.rect.height
                landscape_paper = pw > ph
                rot = 90 if (landscape_page != landscape_paper and o.get("autorotate", True)) else 0
                render_dpi = min(300, max(dpix, dpiy))
                pix = page.get_pixmap(dpi=render_dpi, colorspace=fitz.csGRAY if o.get("gray") else fitz.csRGB, alpha=False)
                im = Image.open(io.BytesIO(pix.tobytes("png")))
                if rot:
                    im = im.rotate(90, expand=True)
                if o.get("fit", True):
                    k = min(pw / im.width, ph / im.height)
                    w, hgt = int(im.width * k), int(im.height * k)
                else:  # actual size: points -> printer pixels
                    w = int(im.width / render_dpi * dpix)
                    hgt = int(im.height / render_dpi * dpiy)
                x = (pw - w) // 2 if o.get("fit", True) else max(0, (pw - w) // 2)
                y = (ph - hgt) // 2 if o.get("fit", True) else max(0, (ph - hgt) // 2)
                dc.StartPage()
                ImageWin.Dib(im).draw(dc.GetHandleOutput(), (x, y, x + w, y + hgt))
                dc.EndPage()
                j["done"] += 1
        dc.EndDoc()
        dc.DeleteDC()
        j["state"] = "gotovo"
        log.info("printed %d pages on %s (offset %s,%s)", j["done"], name, offx, offy)
    except Exception as e:
        log.exception("print failed")
        j["state"] = "greška"
        j["error"] = "Štampa nije uspela. Proveri da li je štampač uključen." if "printer" in str(e).lower() else \
            "Štampa nije uspela. Detalji su u dnevniku."
