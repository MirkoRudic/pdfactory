Važe pravila iz `D:\VAJB\vajb-osnova\PRAVILA.md`. Ovde su arhitektura, zamke i izuzeci.

# PDFabrika

Lokalna zamena za Adobe Reader: čitanje, pretraga, izmene (tekst, ispravka postojećeg teksta, isticanje, oblici, slike, formulari), strane (spajanje, redosled, okretanje, brisanje, izdvajanje, deljenje), OCR, štampa.
Port **8802**, folder `D:\VAJB\pdfabrika`, Python u `.venv`.

## Arhitektura
- `PDFabrika.pyw` — pokretač (Edge `--app` + ikonica pored sata). Argument putanja = otvori fajl (dvoklik na PDF); `--tiho` = start sa Windows-om bez prozora; `--instaliraj`; `--restart`.
- `app/main.py` — FastAPI. Stanje servera su samo otvoreni izvori (`pdfops.SOURCES`, PDF u memoriji) i ubačene slike (`pdfops.IMAGES`).
- `app/pdfops.py` — PyMuPDF: render, tekst, pretraga, `compose()` (radni prostor → novi PDF sa izmenama), OCR.
- `app/static/app.js` — ceo UI. Radni prostor (dokument) živi u pregledaču: `items` (strane: izvor, broj strane, dodatna rotacija, uid), `objects` (izmene po uid strane), `forms`. Čuva se u localStorage, pa slučajno zatvoren prozor ne gubi izmene (server radi dalje).
- Koordinate izmena su **tačke prikazane strane** (rotacija primenjena, gore-levo, 1 = 1 pt). Server ih vraća u PDF prostor preko `page.derotation_matrix`; tekst i slike dobijaju `rotate=page.rotation` da stoje uspravno.
- Čuvanje: `compose()` → upis u `ime.pdf.pfsave` → `os.replace`. Stara verzija ide u `data/rezerva` (poslednjih 20).
- OCR: PyMuPDF ima ugrađen Tesseract, treba mu samo `tessdata` (`pdfabrika/tessdata`: eng iz repoa, srp i srp_latn kopira instalacija iz `kontrolaizbora\podaci\ocr\tessdata`). Dodaje se nevidljiv sloj teksta (render_mode 3), slika strane se ne menja.
- Štampa: `app/printing.py`, pywin32/GDI, sopstveni prozor u app (bez Windows dijaloga štampe).
- Windows: `app/winsetup.py` — prečica, Startup prečica (`--tiho`), registracija kao PDF program (HKCU, `PDFabrika.PDF`), otvaranje stranice Podrazumevane aplikacije. Osvežava se pri svakom pokretanju. Ikonica programa `assets/pdfabrika.ico`, ikonica .pdf fajlova `assets/pdf_fajl.ico` (bela strana, crvena ivica, fabrika sa PDF).
- `PDFabrika.exe` (u `.venv\Scripts`) = kopija venv `pythonw.exe` sa našom ikonicom (pywin32 resource API). Windows ime i ikonicu programa uzima iz .exe-a; sa pythonw.exe piše „Python“. Ako kopija ne pokrene venv (provera pri pravljenju), koristi se pythonw.exe.
- Instalacija: `Instaliraj.vbs` → `instaliraj.pyw` (sistemski Python, tkinter prozor sa napretkom, brava protiv duplog pokretanja) → `.venv`, paketi, srp tessdata → `PDFabrika.pyw --instaliraj`.

## Zamke (izmereno)
- Prva instalacija bez prozora (cmd umanjen) izgleda kao da ništa ne radi; drugi dvoklik je pokretao drugu instalaciju paralelno i pip je pucao (0.1.0). Zato prozor napretka i brava.
- OCR na **sivom** pixmap-u (`csGRAY`) vraća prazan tekst; radi samo RGB.
- `insert_htmlbox` vraća `spare = -1` kad tekst ne staje i tada ništa ne upiše — zato `_text()` probno širi okvir.
- Isticanje kao highlight anotacija se izobliči na rotiranoj strani; zato je providan pravougaonik (shape).
- Ispravka teksta: redakcija samo teksta (`PDF_REDACT_IMAGE_NONE`, `LINE_ART_NONE`), pa novi tekst najbližim instaliranim fontom (`fonts.match`). Pregled u app ima beo okvir; u PDF-u pozadina ostaje kakva jeste.
- Ispravka teksta ne radi na stranama okrenutim u „Strane“ dok se ne sačuva (tekst sloj nije okrenut).

- Mnogi PDF-ovi (Canva, Acrobat izmene) imaju pogrešno mapirana slova: na strani piše „države“, a izvučeni tekst je „drfave“, „ć“ → „c“, „ili“ → „iii“. Zato „Ispravi tekst“ uzima tekst linije OCR-om prikazane strane (`ocr_rect`, srp_latn+srp+eng) kad se slaže sa izvučenim bar 70% bez kvačica (`/fixtext`).
- Ispravka radi na celoj liniji (`lines` u `page_text`): jedna linija je često deset spanova (fontovi, ranije izmene), pa je klik na span pravio mrvice.
- Ispravljena linija ostaje jedna linija: širina se meri pravim fontom (`white-space:pre`); redakcija je skraćena po visini 18% da ne pojede slova susednih linija.
- `.page` ima `overflow: clip`: sa `hidden` fokus u širokom tekst-okviru skroluje stranu bočno (sadržaj strane se pomeri ulevo).
- Zum pri otvaranju je „Automatski“: širina prve strane, najviše 100% (A4 je na širokom ekranu bio 161%). Računa se po strani koja se čita, ne po najširoj; stranica koja se čita se centrira i vodoravno (šire strane prave širu traku).

- „Proveri“ je gledao samo git (lokalno vs GitHub). Kad je kod na disku noviji od pokrenutog servera (kopiran ili povučen dok app radi), pisalo je „Najnovija verzija“ uz staru verziju. Sada `/api/update` poredi i verziju sa diska sa pokrenutom (`restart`), a Ažuriraj tada samo restartuje.
- Nove verzije na laptop idu kroz `git push` + Ažuriraj u app (Windows git ima pristup privatnom repou), ne kopiranjem fajlova.

## Izuzeci od pravila
- UI4: Otvori / Sačuvaj kao / izbor foldera koriste standardni Windows prozor (tkinter) — potrebna je prava putanja fajla.
- O1: nema Windows obaveštenja; OCR i štampa pokazuju napredak u prozoru.

## Testovi
`python tests/test_pdfops.py` (bez pregledača), `tests/ui_check.py` i `tests/ui_flow.py` (Playwright, server na 8802).
