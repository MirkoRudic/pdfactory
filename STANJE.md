# STANJE — PDFactory (26.11.2026)

## Gde smo
- 0.5.0 na grani `qa-2026-11-27` (27.11.): prvi pun QA — 14 popravki, vidi GOTOVO.md; čeka Mirkov pregled pre spajanja u main (spajanje = tiho ažuriranje svima).
- Verzija 0.4.9 (26.11.): izbor podrazumevanog PDF programa kroz Windows „Open with“ nad malim PDF-om (Windows 10).
- 0.4.8: installer čeka da se app ugasi (Restart Manager na Windows 10 nije mogao da je zatvori).
- 0.4.0–0.4.6 (24.11.): sva imena PDFactory, F9, bez Edge mini menija, pretraga centrira pogodak.
- Installer `PDFactory-Setup.exe` pravi GitHub Actions na svaki push; gotov fajl na grani `dist`. Deli se drugarima.

## Otvoreno
- Nije potvrđeno na pravom Windows-u: štampa, Windows prozori za otvaranje/čuvanje, installer i deinstalacija, tiho ažuriranje, gašenje Edge „Help me write“.
- 0.3.6 na drugom računaru: „Update“ ugasio app, verzija ostala ista — uzrok nije utvrđen (od 0.3.8 postoji `setup.log`).
- Kod za staro ime (pre 0.4.0) može da se obriše kad sve kopije pređu 0.4.0.
- Iz QA: potpisivanje ažuriranja i ručno odobrenje objave; gubitak izmena posle restarta servera; P2 spisak u GOTOVO.md.

## Odluke
- UI i brojevi na engleskom (Mirko, 23.11.). Licenca AGPL 3.0 zbog PyMuPDF.
- OCR bez dugmeta: strane bez teksta se prepoznaju u pozadini.
