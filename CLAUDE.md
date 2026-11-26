Važe pravila iz `D:\VAJB\vajb-osnova\PRAVILA.md`. Ovde su arhitektura, zamke i izuzeci. Šta app radi iz ugla korisnika je u `SPEC.md` — svaka izmena ponašanja prvo tamo. Dokle smo stigli: `STANJE.md`.

# PDFactory

Lokalna zamena za Adobe Reader: čitanje, pretraga, izmene (tekst, ispravka postojećeg teksta, isticanje, oblici, slike, formulari), strane (spajanje, redosled, okretanje, brisanje, izdvajanje, deljenje), OCR, štampa.
Port **8802**, folder `D:\VAJB\pdfactory`, repo `MirkoRudic/pdfactory`, Python u `.venv`.

## Arhitektura
- `PDFactory.pyw` — pokretač (Edge `--app` + ikonica pored sata). Argument putanja = otvori fajl (dvoklik na PDF); `--tiho` = start sa Windows-om bez prozora; `--instaliraj`; `--restart`.
- `app/main.py` — FastAPI. Stanje servera su samo otvoreni izvori (`pdfops.SOURCES`, PDF u memoriji) i ubačene slike (`pdfops.IMAGES`).
- `app/pdfops.py` — PyMuPDF: render, tekst, pretraga, `compose()` (radni prostor → novi PDF sa izmenama), OCR.
- `app/static/app.js` — ceo UI. Radni prostor (dokument) živi u pregledaču: `items` (strane: izvor, broj strane, dodatna rotacija, uid), `objects` (izmene po uid strane), `forms`. Čuva se u localStorage, pa slučajno zatvoren prozor ne gubi izmene (server radi dalje).
- Koordinate izmena su **tačke prikazane strane** (rotacija primenjena, gore-levo, 1 = 1 pt). Server ih vraća u PDF prostor preko `page.derotation_matrix`; tekst i slike dobijaju `rotate=page.rotation` da stoje uspravno.
- Čuvanje: `compose()` → upis u `ime.pdf.pfsave` → `os.replace`. Stara verzija ide u `data/rezerva` (poslednjih 20).
- OCR: PyMuPDF ima ugrađen Tesseract, treba mu samo `tessdata` (`tessdata/`: eng iz repoa, srp i srp_latn kopira instalacija iz `kontrolaizbora\podaci\ocr\tessdata`). Dodaje se nevidljiv sloj teksta (render_mode 3), slika strane se ne menja.
- Štampa: `app/printing.py`, pywin32/GDI, sopstveni prozor u app (bez Windows dijaloga štampe).
- Windows: `app/winsetup.py` — prečica, Startup prečica (`--tiho`), registracija kao PDF program (HKCU, `PDFactory.PDF`), otvaranje stranice Podrazumevane aplikacije. Osvežava se pri svakom pokretanju. Ikonica programa `assets/pdfactory.ico`, ikonica .pdf fajlova `assets/pdf_file.ico` (bela strana, crvena ivica, fabrika sa PDF).
- `PDFactory.exe` (u `.venv\Scripts`) = kopija venv `pythonw.exe` sa našom ikonicom (pywin32 resource API). Windows ime i ikonicu programa uzima iz .exe-a; sa pythonw.exe piše „Python“. Ako kopija ne pokrene venv (provera pri pravljenju), koristi se pythonw.exe.
- Instalacija: `Install PDFactory.vbs` → `install.pyw` (sistemski Python, tkinter prozor sa napretkom, brava protiv duplog pokretanja) → `.venv`, paketi, srp tessdata → `PDFactory.pyw --instaliraj`.

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
- Nove verzije na laptop idu kroz `git push` + Ažuriraj u app (repo je javan, 27.11.2026; release API se čita bez tokena), ne kopiranjem fajlova.

- Prazan „Dodaj tekst“ ne ostaje na strani i nije korak za Poništi: okvir se pravi bez koraka, korak nastaje na prvom slovu, a prazan okvir se briše kad izgubi fokus (bio je natpis „Tekst“ na svakom kliku).
- OCR nema podešavanja ni dugme: strane sa slikom i bez teksta (`needsOcr`) se prepoznaju u pozadini čim se fajl otvori (srp_latn+srp+eng); dokument ne postaje „izmenjen“. Strana je zaključana samo dok se čita/piše, sam OCR ide bez brave (inače se strane ne iscrtavaju dok OCR radi).

- Edge prozor app nudi „Ask Edge to help me write“ nad tekst-okvirima: `writingsuggestions="false"` na `<html>` + `--disable-features` sa poznatim imenima Edge funkcija (imena nisu dokumentovana; nije potvrđeno koje deluje).
- Edge mini meni nad označenim tekstom: `edge_quick_search.show_mini_menu = false` u `data/edge/Default/Preferences` (izmereno 24.11.2026: Mirko kliknuo „Hide menu always“, pa poređenje fajla). Upisuje se pre otvaranja prozora kad nijedan prozor app nije otvoren (`edge_prefs`); Edge prepiše fajl pri gašenju.
- Prvi klik na tekst-okvir ga samo izabere (Delete ga briše), klik na već izabran okvir počinje kucanje.

- Podrazumevani program se čita preko `AssocQueryString` (ASSOCSTR_PROGID), ne iz registra: noviji Windows 11 drži izbor u `UserChoiceLatest\\ProgId`, pa je app pisala da nije podrazumevana iako jeste. Promena vrednosti se upisuje u dnevnik.

- Ažuriranje (V5, `_auto_update` u `main.py`): na sat proveri; instalirana kopija tiho preuzme Setup u `data/updates` (`selfupdate.download`), razvojna gleda git. Instalira se samo kad nema otvorenog prozora (`SEEN`: poslednji `/api/inbox` stariji od 5 min) ili pri gašenju (`_update_on_quit`). Setup: `/VERYSILENT /DIR=<app> /RELAUNCH=window|tiho|none /LOG=data\updates\setup.log`; `[Code]` u `setup.iss` bira da li i kako se app ponovo pokreće (`--updated`, `--tiho`). Release pravi workflow na svaki push (`gh release create v<verzija>`), repo mora biti javan.
- 0.3.6 na drugom računaru: „Update“ je ugasio app, a verzija ostala ista. Uzrok nije utvrđen (nema loga installera u 0.3.6); od 0.3.8 installer piše `data\updates\setup.log`, a `PrivilegesRequiredOverridesAllowed` je izbačen (izbor „za sve korisnike“ bi tražio administratora, a tiho ažuriranje ga nema).
- 0.4.7 na Windows 10: „Update now“ → installer pokrenut odmah, app (bez prozora, pythonw) još radi, Restart Manager ne može da je ugasi, a sa `/SUPPRESSMSGBOXES` Inno bira Abort (`setup.log`). Od 0.4.8 `selfupdate.run` pokreće skriven PowerShell koji čeka da se PID app ugasi pa tek onda installer.
- Sadržaj dijaloga se pomerao bočno (selekcija/prevlačenje skroluje `overflow:auto` vodoravno): `.dlg .body` ima `overflow-x:hidden`, a `modal()` vraća `scrollLeft` na 0.
- Deinstalacija iz Settings: instalirana kopija pokreće `unins000.exe /SILENT` ~2 s posle gašenja app (`winsetup.uninstall`); razvojna samo `unregister()` + prečice.
- Izbor podrazumevanog: Windows 10 Settings → Default apps nema pretragu, a .pdf je duboko u listi. Zato `open_default_apps()` otvara Windows „How do you want to open this file?“ (`SHOpenWithDialog` nad malim `data/tmp/choose-default.pdf`, OAIF 0x05), a Settings samo ako on ne uspe. 0.4.7 je koristio `.pdf` + OAIF 0x23: na Windows 10 to samo pokaže „To change your default apps, go to Settings“ i vrati S_OK (izmereno). Kad korisnik izabere PDFactory, Windows otvori marker: pokretač ga obriše i samo dovede prozor napred.
- Installer je za opciju „default“ otvarao Windows podešavanja pre Finish, bez objašnjenja. Sada `--want-default` samo upiše `data/ask_default`, a app na startu pita u svom dijalogu (`/api/default-check` → `ask`).
- 0.4.0: sva imena su PDFactory (ProgID `PDFactory.PDF`, `/health` `pdfactory`, localStorage `pdfactory.*`, dnevnik `pdfactory_*.log`). Prvo ime (do 0.3.9) briše `winsetup.remove_first_name()` pri startu; ako je ono bilo podrazumevani PDF program, app jednom pita da se izabere PDFactory (Windows izbor vezuje za ProgID). Izmereno na laptopu: posle brisanja starog ProgID-a Windows je za 3 minuta vratio Acrobat, a `AssocQueryString` je u međuvremenu javljao PDFactory (iz OpenWithProgids) — zato se izbor čita iz registra (`_user_choice`). Migracija dnevnika u pokretaču i localStorage u `app.js`. Sve to može da se obriše kad sve kopije pređu 0.4.0.
- Prijava problema iz app je uklonjena u 0.3.1 (nije potrebna za sada); kod je u istoriji gita (0.3.0: `_redact`, `/api/report`, mailto).

- F9 (`localguard`): server odbija tuđ Host (DNS rebinding) i zahtev koji menja stanje sa tuđe stranice; bez toga bi bilo koja stranica u pregledaču mogla da traži `/api/open` (čitanje fajlova) ili `/api/save` (upis).

## Izuzeci od pravila
- T1, T3: UI je na engleskom (Mirko, 23.11.2026), brojevi engleski (`1,200.50`). Komentari i CLAUDE.md ostaju kako jesu.
- Licenca: AGPL 3.0 zbog PyMuPDF (`LICENSE`, Settings → About).
- Deljenje: `PDFactory-Setup.exe` pravi GitHub Actions (`.github/workflows/setup.yml`, Inno Setup `packaging/setup.iss`) na svaki push: svoj Python (embeddable + tkinter iz punog), `python\PDFactory.exe` sa ikonicom (rcedit), srp tessdata, čarobnjak (folder, prečice, start sa Windows-om, podrazumevani PDF), deinstalacija (`--uninstall` briše registar). Gotov fajl je na grani `dist`. Instalirana kopija nema `.git`; ažurira se iz GitHub Releases (`selfupdate.py`, V5); `winsetup.INSTALLED` = postoji `python\PDFactory.exe`.
- Ranije za drugare: zip bez `.git`, `.venv`, `data`, sa srp tessdata; `Install PDFactory.vbs` instalira Python preko winget ako ga nema. Fajl skinut sa interneta: Windows pri dvokliku jednom pita „Open“ (nepotpisan fajl); bez toga samo uz kupljen sertifikat za potpisivanje koda. Ta stara zip kopija bez `.git` nema ažuriranje.

## Napomene
- Otvori / Sačuvaj kao / folder: comdlg32 preko ctypes (tkinter nema u ugrađenom Python-u instalirane kopije); po UI4 dozvoljeno.
- OCR i štampa: napredak u prozoru, bez Windows obaveštenja (O1).

## Testovi
`python tests/test_pdfops.py` (bez pregledača), `python tests/test_qa.py`, `python tests/test_qa_api.py`, `node tests/test_qa_js.js` (nalazi QA 27.11.2026); `tests/ui_check.py` i `tests/ui_flow.py` (Playwright, server na 8802; zastareli: ui_flow traži dugme „Recognize text“ kog više nema, ui_check je popravljen).
