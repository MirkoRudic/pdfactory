# ATTEMPTS — šta je probano (R21)

Pre svakog predloga rešenja pročitaj ovo. Ono što je palo ne predlaže se ponovo bez novog razloga.
Format: datum / verzija — šta je probano → **radi / ne radi / delimično** — zašto.

## Ažuriranje instalirane kopije
- 25.11 / 0.4.7 — Setup pokrenut odmah iz app → **ne radi**: app (pythonw) još radi, Restart Manager ne može da je ugasi, Inno sa `/SUPPRESSMSGBOXES` bira Abort.
- 25.11 / 0.4.8 — skriven PowerShell čeka PID app pa pokreće Setup → **ne radi**: na računaru u radionici installer se nikad nije pokrenuo (nema setup.log).
- 26.11 / 0.4.10 — Setup dobija `/WAITPID=<pid>` i sam čeka u `InitializeSetup` → **čeka potvrdu** na pravom računaru.
- 0.3.6 — Update ugasio app, verzija ostala ista → uzrok nije utvrđen; od 0.3.8 postoji `data\updates\setup.log`.

## Podrazumevani PDF program
- 0.4.7 — `.pdf` + OAIF 0x23 → **ne radi** na Windows 10 (samo poruka „go to Settings“).
- Čitanje izbora iz registra (`UserChoice`) → **ne radi** na novom Windows 11 (`UserChoiceLatest`); `AssocQueryString` → radi, uz rezervu iz registra posle promene ProgID-a.
- Installer otvara Windows podešavanja pre Finish → **loše** (bez objašnjenja); sada app pita u svom dijalogu.

## Izmene i OCR
- Isticanje kao highlight anotacija → **ne radi** na rotiranoj strani (izobličeno); providan pravougaonik radi.
- Ispravka teksta po spanu → **ne radi** (mrvice, jedna linija je deset spanova); po celoj liniji radi.
- OCR na sivom pixmap-u → **ne radi** (prazan tekst); RGB radi.
- `.page { overflow: hidden }` → **ne radi** (fokus skroluje stranu bočno); `clip` radi.
- 27.11 QA — OCR samo za strane sa < 20 znakova → **ne radi** (svako otvaranje + čuvanje dodaje sloj); „bez ikakvog teksta“ → **ne radi** (preskače skenove sa zaglavljem); sada: vidljivo < 20 i bez nevidljivog sloja.
- 27.11 QA — uspravna linija po obliku okvira (visina > 1,5 × širina) → **ne radi** (blokira „1.“, „a)“); po pravcu teksta (`dir`) radi.
