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
- Popravljeno u 0.5.1 (27.11): izmene posle restarta servera (kopije u `data/session`), slika „na svim stranama“ posle brisanja strane, PowerShell navodnici ’ ‘ (`winsetup._psq`), zastareli moduli (update 1.2, base.css 1.4, F10 komentari), prazni `except` sa komentarom, izlaz kroz `hard_exit` (čisti `data/tmp`, poslednji red dnevnika), `--instaliraj` pita u app umesto Windows prozora, `ui_flow.py` bez dugmeta „Recognize text“.
- Ostalo: sitne razlike SPEC/AGENTS (D5–D16).

**Nije provereno (Linux):** štampa, Windows dijalozi, installer i deinstalacija, ikonica pored sata, Edge meniji, tiho ažuriranje instalirane kopije, srpski OCR.

**Potrošnja:** 11 agenata (5 pregled, 4 potvrda, 1 potvrda UI, 1 krug 2), ~2,1 M tokena agenata; ~1 h 10 min.
