# PDFactory — specifikacija

Šta aplikacija radi, iz ugla korisnika. Svaka izmena se prvo upiše ovde, pa u kod.
Oblik scenarija: **kad uradim X → desi se Y**. Tehnika i zamke su u `CLAUDE.md`.

## Svrha
Lokalna, besplatna zamena za Adobe Reader na Windows-u: čitanje, izmene, strane, OCR, štampa. Sve radi na računaru, bez naloga i interneta (internet samo za proveru nove verzije).

## Ciljni korisnik
Windows 10/11 korisnik bez tehničkog znanja: ne zna za Python, git ni portove, instalira dvoklikom.

---

## 1. Instalacija i Windows

- Opcija „Make PDFactory the default“ u čarobnjaku → instalacija ne otvara Windows podešavanja; pri prvom pokretanju app pita sa objašnjenjem („Windows asks you to confirm…“) i tek na „Open Windows settings“ otvara izbor.
- Dvoklik na `PDFactory-Setup.exe` → pravi čarobnjak sa ikonicom: izbor foldera, prečice, start sa Windows-om, podrazumevani PDF program. Bez cmd prozora, bez administratorskih prava.
- Windows pri prvom dvokliku jednom pita „Open“ (nepotpisan fajl) → to je jedino pitanje van čarobnjaka.
- Deinstalacija (Windows → Aplikacije) → briše program, prečice, registraciju i `data`.
- Start sa Windows-om uključen → app se pokrene bez prozora, samo ikonica pored sata.
- Dvoklik na PDF (kad je podrazumevani) → fajl se otvori u PDFactory; ako app već radi, otvori se u istom prozoru.
- Ime i ikonica u Windows-u su „PDFactory“ (nikad „Python“). PDF fajlovi imaju svoju ikonicu: bela strana, crvena ivica, fabrika sa „PDF“.
- Settings → Windows → „Set as default“ → Windows prozor za izbor se otvori **ispred** app; posle izbora Settings sam pokaže „PDFactory is the default“.
- Server se ne pokrene za 15 s → fajl se otvori u Edge-u, da korisnik ne ostane bez ičega.

## 2. Otvaranje i čitanje

- Open (krajnje levo u zaglavlju), Ctrl+O, prevlačenje fajla, nedavni fajlovi na početnom ekranu → dokument se otvori.
- Pri otvaranju zum je „Automatski“: prva strana stane po širini, najviše 100%. Strana je centrirana i vodoravno.
- Dugme 100% pored − i + → odmah vraća na 100%. Ctrl+plus / Ctrl+minus / Ctrl+0 rade isto.
- Pretraga (Ctrl+F, F3 sledeće) → pogoci istaknuti; pogodak se postavi na sredinu prozora.
- Leva kolona: desni klik na stranu → Copy page as image (puna rezolucija, 300 dpi), Rotate right, Move up/down, Delete page; prevlačenje menja redosled. Nigde nema menija pregledača, osim nad poljem za kucanje i označenim tekstom.
- Skenirane strane bez teksta → OCR sam krene u pozadini (srpska latinica, ćirilica, engleski). U podnožju piše „Recognizing text x%“. Nema podešavanja ni dugmeta. Dokument zbog OCR-a **ne** postaje izmenjen.
- Slučajno zatvoren prozor → pri ponovnom otvaranju sve izmene su tu.

## 3. Izmene (Edit)

Alati: Move and resize, Add text, Edit text, Highlight, Shape, Image, Fill form.

- **Add text**: klik na stranu → okvir za kucanje. Ništa ne ukucam i kliknem dalje → na strani **ne ostaje ništa** (ni natpis „Tekst“) i nema koraka za Undo.
- Izbor fonta → svi instalirani fontovi, svaki prikazan svojim izgledom; veličina, boja, podebljano, kurziv, poravnanje.
- **Edit text**: klik na postojeći tekst → menja se cela linija, istim (ili najbližim) fontom i veličinom; podebljano i kurziv prate original, a zamena za font koji nije instaliran nikad nije teži rez iste porodice (npr. „Black“ za običan tekst). Linija ostaje jedna linija, susedne linije ostaju netaknute. Radi i na PDF-ovima sa pogrešno mapiranim slovima (Canva, Acrobat): u polju je tekst kakav se vidi na strani, ne „drfave“.
- **Highlight**: providan pravougaonik, ispravan i na okrenutim stranama.
- **Shape**: pravougaonik, elipsa, linija, strelica; boja, debljina, ispuna.
- **Image**: ubaci sliku → pomeranje, promena veličine, sečenje (crop), okretanje pod bilo kojim uglom, preslikavanje, providnost, iza teksta.
- **Fill form**: polja formulara se popunjavaju na strani.
- Prvi klik na element ga izabere; klik na već izabran tekst-okvir počinje kucanje.
- Esc → poništi izbor. Delete → obriše izabrani element. Strelice → pomeraju ga. Ctrl+C/X/V/D → kopiraj, iseci, nalepi, dupliraj.
- Edge ne nudi „Help me write“ nad poljima i ne pokazuje svoj meni nad označenim tekstom.

## 4. Strane (Pages)

- Prevlačenje → novi redosled. Okretanje, brisanje, izdvajanje u novi PDF, deljenje po opsegu (npr. `1-3, 5`), dodavanje drugog PDF-a ili slike.
- Ctrl+A → izabere sve strane.

## 5. Undo / Redo

- Dugmad su levo u zaglavlju, odmah posle Open. Ctrl+Z / Ctrl+Y (ili Ctrl+Shift+Z).
- Važe za **sve**: izmene na strani, brisanje i premeštanje strana, okretanje, formulare.

## 6. Čuvanje i štampa

- Ctrl+S / Save → upiše se u isti fajl; prethodna verzija ide u rezervu (poslednjih 20). Save as → standardni Windows prozor.
- Štampa (Ctrl+P) → sopstveni prozor u app: štampač, strane, broj kopija, boja/sivo, obostrano, 1 ili 2 strane po listu, uklopi ili stvarna veličina. Napredak se vidi u prozoru.

## 7. Settings

- **Appearance**: tamna / svetla tema.
- **Windows**: start sa Windows-om (prekidač), podrazumevani program (stanje + dugme)
- **Log**: veličina, „Show log“ otvara dnevnik u posebnom prozoru (filter, samo problemi), brisanje starijih od 30 dana. Dnevnik nije izlistan u samim podešavanjima.
- **About**: kako app radi, „Made by Mirko with Claude Opus 5.5 (Anthropic)“, ispod toga „More“ koji otvara motore i licence (AGPL 3.0 + komponente).
- **Version**: ispod verzije stanje poslednje provere (automatske ili ručne): „Up to date · checked 14:40“, „New version X“ ili „Check failed“. Dugme „Check for updates“; kad ima nova, dugme postaje „Update to X“ — jedan klik ažurira i restartuje; posle ponovnog otvaranja piše „Updated: x.y.z“.
- **Uninstall** (poslednji deo): potvrda → instalirana kopija se ukloni cela (PDF fajlovi ostaju); razvojna kopija skida prečice, start sa Windows-om i PDF povezivanje, folder ostaje.
- Nema liste prečica ni OCR podešavanja.
- Sadržaj podešavanja i drugih prozora se ne pomera bočno (ni mišem, ni prevlačenjem, ni selekcijom); skroluje se samo uspravno.

## 8. Ažuriranje (bez klikanja)

- Nova verzija se sama pronađe (na startu i svakog sata) i tiho preuzme u pozadini. Nema trake ni pitanja.
- Instalira se sama kad nijedan prozor app nije otvoren (npr. posle starta sa Windows-om, app samo pored sata) ili kad korisnik ugasi app. Otvoren prozor se nikad ne zatvara zbog ažuriranja.
- Settings → Version: „New version X · installs by itself when PDFactory is closed“ i dugme „Update now“ za one koji ne žele da čekaju (prozor ostaje, sam se osveži kad je nova verzija gotova).
- Nema interneta → ništa se ne prikazuje, nema greške.

## 9. Izgled

- Zaglavlje: levo Open | Undo Redo; sredina Read / Edit / Pages; desno Save, Print, Settings, Quit. Bez logoa i imena u zaglavlju.
- Crvena boja (Acrobat stil), simetrično i poravnato. UI na engleskom, brojevi `1,200.50`.
- Quit iz app ili ikonice pored sata sa neizmenjenim dokumentom → izlaz; sa izmenjenim → pita.

---

## Namerno ne radi (non-goals)
- Beleške (sticky notes), crtanje rukom, potpis, „pokrij“ (redakcija kao alat).
- Nalozi, oblak, sinhronizacija, telemetrija, slanje dokumenata bilo kome.
- OCR podešavanja, lista prečica u Settings.
- Mac i Linux (za sada samo Windows).
- Windows obaveštenja (napredak je u prozoru app).
- Prijava problema iz app (za sada).

## Otvoreno (nije potvrđeno na pravom Windows-u)
Štampa, Windows prozori za otvaranje/čuvanje, installer i deinstalacija, tiho ažuriranje, gašenje Edge „Help me write“.
