# GOTOVO — PDFactory

## Pun QA, 27.11.2026 (grana `qa-2026-11-27`, verzija 0.5.0) — prvi prolaz po R20
5 pregledača (korisnik po SPEC-u u pregledaču, logika, pravila, bezbednost, dokumentacija) → 4 agenta za potvrdu → popravke → krug 2 (pregled popravki + bezbednost nad promenjenim fajlovima) → popravke kruga 2.

**Popravljeno (svaka sa testom koji pada bez popravke; `tests/test_qa.py`, `test_qa_api.py`, `test_qa_js.js`):**
- Čuvanje posle brisanja / redosleda / okretanja strana gubilo je sadržaj (bookmarks), metapodatke i unutrašnje linkove.
- Spojeni formulari sa istim imenom polja: vrednost drugog se gubila. Radio grupa: čuvale su se sve opcije kao izabrane.
- OCR: svako otvaranje + čuvanje dodavalo je još jedan nevidljiv sloj (dupli tekst u pretrazi); reči na okrenutom skenu imale su pogrešnu širinu.
- Okretanje strane spljoštavalo je ubačenu sliku.
- Podela je tiho prepisivala postojeći fajl istog imena (sada ide u `data/rezerva`).
- Podešavanje teme se upisivalo u stranicu bez provere (ubacivanje HTML-a).
- Pokretač je brisao korisnikov fajl `choose-default.pdf` bilo gde (sada samo marker u `data/tmp`).
- Ažuriranje git kopije zatvaralo je prozor i otvaralo nov (V2/V5); prozor se sad sam osveži i kad restart nije on tražio.
- Poslednja radnja se nije čuvala za slučajno zatvoren prozor; Undo posle vraćanja je brisao oznaku „nesačuvano“.
- Dugmad u dijalozima bila su na srpskom u engleskom UI (dialog.js 1.1).
- Edit text na uspravnoj liniji (bočni tekst, strana sa rotacijom) ostavljao je ostatke i pisao preko susednih linija — sada poruka.
- Dokumentacija: deljenje, Quit (P4), ažuriranje instalirane kopije, javni repo, testovi.

**Ostalo (nije popravljeno, odluka ili veći posao):**
- **Ažuriranje nije potpisano** (P0 rizik): app tiho instalira poslednji .exe sa GitHub-a uz proveru samo veličine; svaki push sa novom verzijom ide svima bez ljudske provere. Predlog: SHA256/potpis u release-u + ručno odobrenje objave. Isto za build: akcije i preuzimanja bez fiksnih verzija.
- Posle restarta servera (ažuriranje dok je prozor zatvoren): nesačuvane izmene iz spojenih dokumenata i ubačene slike se gube bez poruke.
- Slika „na svim stranama“ nestaje kad se obriše strana na koju je ubačena (Undo je vraća).
- PowerShell navodnici za putanje sa ’ (selfupdate).
- P2: zastareli moduli (update.py 1.0, base.css 1.0, applog/tempdir/runlock bez F10 komentara), prazni `except` bez komentara, `os._exit` preskače čišćenje `data/tmp` i poslednji red dnevnika, `--instaliraj` otvara Windows prozor, sitne razlike SPEC/CLAUDE (D5–D16).
- `tests/ui_flow.py` traži dugme „Recognize text“ kog više nema.

**Nije provereno (Linux):** štampa, Windows dijalozi, installer i deinstalacija, ikonica pored sata, Edge meniji, tiho ažuriranje instalirane kopije, srpski OCR.

**Potrošnja:** 11 agenata (5 pregled, 4 potvrda, 1 potvrda UI, 1 krug 2), ~2,1 M tokena agenata; ~1 h 10 min.
