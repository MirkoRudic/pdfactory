"""Builds test PDFs: text pages, a rotated page, a form, a scanned (image-only) page."""
import sys, pymupdf as f
from pathlib import Path
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
d = f.open()
for i in range(3):
    p = d.new_page()
    p.insert_text((72, 90), f"Ugovor o produkciji - strana {i+1}", fontsize=18)
    p.insert_text((72, 130), "Iznos: 100.000 RSD. Rok isporuke je 30 dana.", fontsize=12)
d[2].set_rotation(90)
w = f.Widget(); w.field_name = "ime"; w.field_type = f.PDF_WIDGET_TYPE_TEXT; w.rect = f.Rect(72, 200, 300, 222); d[0].add_widget(w)
c = f.Widget(); c.field_name = "saglasan"; c.field_type = f.PDF_WIDGET_TYPE_CHECKBOX; c.rect = f.Rect(72, 240, 88, 256); d[0].add_widget(c)
d.save(out / "ugovor.pdf")
# scanned page: render text to image only
t = f.open(); tp = t.new_page(); tp.insert_text((72, 120), "Racun broj 42 za snimanje spota", fontsize=22)
pix = tp.get_pixmap(dpi=200)
s = f.open(); sp = s.new_page(width=tp.rect.width, height=tp.rect.height); sp.insert_image(sp.rect, pixmap=pix)
s.save(out / "skenirano.pdf")
print("ok")
