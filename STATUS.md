# STANJE — PDFactory (27.11.2026)

## Gde smo
- 0.5.1 (27.11.): ostaci QA — izmene ostaju posle restarta servera (`data/session`), slika na svim stranama, PowerShell navodnici, moduli, `hard_exit`, `--instaliraj` pita u app.
- 0.5.0 (27.11.): prvi pun QA — 14 popravki (vidi QUALITY_REPORT.md), spojeno u main uz 0.4.10 (Setup sam čeka da se app ugasi, /WAITPID).
- Verzija 0.4.9 (26.11.): izbor podrazumevanog PDF programa kroz Windows „Open with“ nad malim PDF-om (Windows 10).
- 0.4.8: installer čeka da se app ugasi (Restart Manager na Windows 10 nije mogao da je zatvori).
- 0.4.0–0.4.6 (24.11.): sva imena PDFactory, F9, bez Edge mini menija, pretraga centrira pogodak.
- Installer `PDFactory-Setup.exe` pravi GitHub Actions na svaki push; gotov fajl na grani `dist`. Deli se drugarima.

## Otvoreno
- Nije potvrđeno na pravom Windows-u: štampa, Windows prozori za otvaranje/čuvanje, installer i deinstalacija, tiho ažuriranje, gašenje Edge „Help me write“.
- 0.3.6 na drugom računaru: „Update“ ugasio app, verzija ostala ista — uzrok nije utvrđen (od 0.3.8 postoji `setup.log`).
- Kod za staro ime (pre 0.4.0) može da se obriše kad sve kopije pređu 0.4.0.
- Iz QA: potpisivanje ažuriranja i ručno odobrenje objave (Mirko: kasnije); fiksne verzije akcija u workflow-u.

## Odluke
- UI i brojevi na engleskom (Mirko, 23.11.). Licenca AGPL 3.0 zbog PyMuPDF.
- OCR bez dugmeta: strane bez teksta se prepoznaju u pozadini.
