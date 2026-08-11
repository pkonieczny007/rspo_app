# CLAUDE.md — kontekst projektu RSPO

Plik dla asystenta AI pracującego nad tym katalogiem. Zawiera to, czego **nie
widać z samego kodu**: po co to powstało, jakie decyzje zapadły i dlaczego, oraz
o co już się potknęliśmy. Rzeczy odczytywalne z plików (lista funkcji, struktura
katalogów) świadomie pomijamy — od tego jest `README.md`.

---

## 1. Co to jest

Osobna aplikacja Flask do zarządzania bazą placówek oświatowych z **RSPO**
(Rejestr Szkół i Placówek Oświatowych, `rspo.gov.pl`). Wgrywasz plik z rejestru,
widzisz wszystkie placówki, ustawiasz i poszerzasz rejony działania,
wyprowadzasz wykaz.

**Klient: SILESIA 3D** — zajęcia druku 3D dla szkół i przedszkoli na Śląsku.
Osoby, które padają w komentarzach:
- **Wojtek** — właściciel. Chce mieć „całą aktualną bazę szkół" (pytanie o zasięg
  i potencjał, nie o funkcję).
- **Kasia** — koordynatorka. Chce **krótkiej listy rejonów**, po których realnie
  jeżdżą trenerzy. Do 09.08.2026 pobierała CSV z rspo.gov.pl i **ręcznie
  przepisywała** interesujące szkoły do arkusza. To ta praca miała zniknąć.
- **DT = dzień technologiczny** — pokazowy dzień w szkole, po którym otwierają
  się grupy zajęć cyklicznych. Centralne pojęcie domeny (żyje w aplikacji
  leadów, nie tutaj).

**To narzędzie NIE jest bazą sprzedażową.** Leady, statusy, historia kontaktów
i grafik trenerów są w `..\leady_app_v5`. Tu jest wyłącznie lustro rejestru.

### Dlaczego osobno, a nie ekran w aplikacji leadów

Inna praca i inny rytm. Aplikacja leadów obsługuje codzienną sprzedaż; tutaj raz
w miesiącu ktoś wgrywa 42-megabajtowy plik i decyduje, czy poszerzyć teren.
Osobno znaczy, że próba z nowym rejonem nie może zepsuć bazy, na której
pracują handlowcy. **Docelowo** ten kod wchodzi do aplikacji leadów jako ekran
koordynatora — dlatego `magazyn.py`, `rejony.py` i `zapytania.py` nie wiedzą nic
o Flasku.

---

## 2. Uruchomienie

```powershell
python app.py                 # http://127.0.0.1:5310
python test_rspo.py           # 39 sprawdzeń, wszystkie muszą przechodzić
```

**Port 5310, nie 5301** — 5301 zajmuje aplikacja leadów, 5000 zajmuje połowa
narzędzi deweloperskich.

Baza: `dane/rspo.db`. Inny katalog: `$env:RSPO_DATA="D:\gdzies"`.
Wgrane pliki lądują w `dane/wgrane/` ze znacznikiem czasu — **zostają na dysku
celowo**, żeby dało się wrócić do *tego* pliku, gdy raport pokaże coś dziwnego.

Kopia bazy (nie tylko przy wdrożeniu — flagi „objęta”, notatki i poszerzone
rejony nie wracają z żadnego pliku rejestru):

```powershell
python narzedzia\kopia.py zrob      # dane\kopie\rspo_RRRR-MM-DD_GGMM.db
python narzedzia\kopia.py lista
python narzedzia\kopia.py przywroc --z dane\kopie\rspo_….db
```

**Na serwerze aplikację uruchamia gunicorn (`app:app`), więc `main()` nie
wykonuje się ani razu.** Schemat bazy i rejony startowe zakłada dlatego
`przygotuj_baze()` wywoływane **przy imporcie modułu** `app.py` — przeniesienie
tego z powrotem do `main()` „bo tam jest start” kończy się na produkcji
komunikatem `no such table: placowki`.

Wdrożenie na VPS: **`docs/WDROZENIE.md`** (domena `rspo.silesia3d.site`, port
5310, kontener `rspo_app`, hasło w nginx). Aktualizacja później: `./wdroz.sh`.

---

## 3. Trzy decyzje, na których stoi całość

**1. `rspo` jest kluczem głównym tabeli `placowki`.** Nie `id`, nie nazwa.
Szkoły zmieniają nazwy („SP nr 12" → „SP nr 12 im. Jana Pawła II"), adresy
i dyrektorów; stały jest tylko numer. Dzięki temu obietnica „kolejne wgranie
dogrywa nowe, ale nie robi duplikatów" nie jest starannością w kodzie, którą da
się przeoczyć przy następnej poprawce — jest warunkiem narzuconym przez bazę.
**Nie zamieniać na sztuczne `id` z `rspo UNIQUE`** — to wygląda tak samo
i nie jest tym samym.

**2. Rejon to lista obszarów, nie kolumna na placówce.** `rejon_obszary` trzyma
pary (`powiat`|`gmina`, nazwa), a `placowka_rejon` jest przeliczane funkcją
`rejony.przelicz()` po każdej zmianie. Poszerzenie terenu to dopisanie jednej
linijki i ułamek sekundy zamiast przepisania tysiąca wierszy.

**Gmina bije powiat.** Reguła żyje w jednym miejscu — w kolejności dwóch
`INSERT`-ów w `przelicz()`: najpierw powiaty, potem gminy z `INSERT OR REPLACE`.
Dzięki temu Knurów zostaje przy swoim rejonie, nawet gdy cały powiat gliwicki
trafi kiedyś do „Gliwic". Jest na to test.

**3. Baza jest lustrem rejestru — z dokładnie jednym wyjątkiem.** Rejestr
nadpisuje swoje pola (inaczej po pół roku nie wiadomo, co jest aktualne, a co
naszym starym odbiciem). Import **nigdy** nie dotyka trzech naszych kolumn:
`objeta`, `notatka`, `pierwszy_import`.

> To jest odwrotnie niż w aplikacji leadów, gdzie import uzupełnia **tylko puste
> pola** (`importer.py:344–349`), bo tam ręczna poprawka handlowca jest
> cenniejsza od pliku. Dwie różne bazy, dwie różne zasady — nie ujednolicać.

⚠️ **Wyjątek na przyszłość, przy imporcie z API:** trzy kolumny (`faks`,
`jezyki`, `rodzaj_miejscowosci`) w `PlacowkaDTO` **nie występują w ogóle**.
Import z API musi je zostawić **niezmienione**, a nie wyczyścić — inaczej dane
z pliku CSV zniknęłyby przy pierwszym odświeżeniu przez API.

---

## 4. Skąd biorą się dane

**Plik CSV z wyszukiwarki `rspo.gov.pl/institutions`.** Publiczny, klikany ręką,
54 kolumny, cała Polska to 56 190 wierszy i ~42 MB. Wzorzec, na którym wszystko
sprawdzano:
`..\8.08.2026-home\plik rspo\rspo_2026_08_08.csv`

**API `api.rspo.gov.pl`** — rozpoznane 11.08 z **oficjalnych plików CIE**
pobranych do `tmp/zrodla/` (OpenAPI 3.1.0, wersja API 1.2.0, regulamin, wzór
wniosku). Pełne ustalenia: **`tmp/API_RSPO_notatki.md`** — czytać przed każdą
pracą nad API, żeby nie zgadywać drugi raz. Skrót:

- REST + JSON, **HTTP Basic Auth** (login i hasło, nie klucz), łączyć się
  **wyłącznie po `https://`** — spec podaje serwer bez S, a Basic po czystym HTTP
  to hasło otwartym tekstem przy każdym zapytaniu
- dostęp **bezpłatny i na czas nieokreślony**; wniosek mailem na `rspo@cie.gov.pl`,
  rozpatrzenie do 14 dni. **Wniosek nie jest jeszcze wysłany** — szkic gotowy
  w `tmp/wniosek-mail-szkic.md`, brakuje danych rejestrowych klienta
- stare API `api-rspo.men.gov.pl` **wyłączone 02.03.2026** — domena się nie
  rozwiązuje; kto pisał integrację na starym, ma ją martwą
- **nie ma filtra „zmienione od daty"** → każde odświeżenie to pobranie całości
  i porównanie po naszej stronie. `magazyn.py` już dokładnie to robi, więc API
  wpina się bez przebudowy
- regulamin pozwala CIE zawiesić lub cofnąć dostęp i nie gwarantuje dostępności
  (§4, §5) → **ścieżka z plikiem CSV zostaje na stałe jako wyjście awaryjne**,
  nie jest etapem przejściowym

**Otwarte dane z `dane.gov.pl` (zbiór 839) to wykazy z lat 2013–2017** — martwe,
sprawdzone, odpada.

### Czego w pliku NIE MA — sprawdzone kolumna po kolumnie

**Współrzędnych geograficznych.** 54 kolumny i ani jednej z szerokością/długością.
Jest za to `Kod terytorialny gmina` (TERYT), wypełniony w **6 116 z 6 116**
rekordów — i to jest klucz do mapy rejonów bez żadnego geokodowania.

**API je ma** — potwierdzone w specyfikacji, nie z dokumentacji ze słyszenia:
`PlacowkaDTO.geolokalizacja[]` → `GeotagDTO {latitude, longitude}`
(`tmp/zrodla/api-docs.yaml`, linie 1002–1008 i 1181–1185). To jest ta jedna
rzecz, dla której warto składać wniosek. Kolumny `lat`/`lon` czekają puste
w schemacie — patrz sekcja 9, etap 2 mapy.

**Daty likwidacji.** Filtr placówek zlikwidowanych w `plik.py` działa, ale nie
odpalił się ani razu — eksport z wyszukiwarki zawiera wyłącznie czynne placówki,
kolumna jest pusta w całym pliku. Skutek: **„placówka zniknęła z rejestru"
wykrywamy przez porównanie z poprzednim stanem bazy**, nie przez odczyt z pliku.
Filtr zostaje jako zabezpieczenie na wypadek innego eksportu.

---

## 5. Decyzje projektowe, których nie widać z kodu

**Zniknięte oznaczamy, nie kasujemy.** Placówka znika z rejestru także wtedy, gdy
się przekształci albo połączy; w aplikacji leadów wisi na niej historia
kontaktów i umówione DT. Kasowanie jest nieodwracalne, oznaczenie — nie.

**Bezpiecznik przy zniknięciach (`magazyn.PROG_ZNIKNIEC`, `MIN_ZNIKNIEC`).**
Gdyby ktoś wgrał plik przefiltrowany w wyszukiwarce (np. same Katowice), naiwne
porównanie oznaczyłoby całą resztę województwa jako zniknięcie. Oznaczamy więc
tylko, gdy ubytek jest mały **jednocześnie** bezwzględnie (≤25) i względnie
(≤20% bazy). Inaczej narzędzie nie robi nic i **mówi dlaczego** — lepszy
komunikat niż cicha katastrofa. Sam procent nie wystarczał: na małej bazie
testowej odpalał się przy każdym normalnym ubytku, czyli test sprawdzałby, że
mechanizm NIE działa.

**Grupy typów rozpoznawane po słowach kluczowych, nie po sztywnej liście.**
Rejestr ma w samym śląskim **43 różne typy** placówek — lista rozwijana z 43
pozycjami to spis treści, nie filtr. Grupy w `db.GRUPY_TYPOW` dopasowują po
fragmentach nazwy, więc gdy rejestr doda „Przedszkole integracyjne", wpadnie do
przedszkoli samo, zamiast wylądować w „innych" i zniknąć koordynatorce z oczu.
**Kolejność na liście ma znaczenie** — pierwsza pasująca grupa wygrywa, dlatego
„Ogólnokształcąca szkoła muzyczna I stopnia" trafia do artystycznych, a nie do
podstawówek. `zapytania._sql_grup()` odtwarza tę samą kolejność w SQL-u, żeby
ekran i eksport nie liczyły inaczej niż ekran rejonów.

**Filtry siedzą w adresie, nie w sesji.** Adres da się wysłać mailem („zobacz te
96 placówek w Bytomiu") i da się do niego wrócić przyciskiem wstecz. Filtr
schowany w sesji wygląda jak brakujące dane — nikt nie wie, czemu widzi 300
zamiast 6 000. Helper `link()` w `app.py` podmienia jeden parametr i zachowuje
resztę; bez niego kliknięcie w nagłówek kolumny gubiłoby wybrany rejon.

**Eksport i ekran używają TEGO SAMEGO `zapytania._warunki()`.** Gdyby eksport
budował warunki po swojemu, prędzej czy później oddałby inny zbiór niż ten, który
koordynatorka widzi — a to jest błąd, którego nikt nie zauważa, dopóki nie jest
za późno.

**Zero pobierania z zewnątrz.** Żadnych czcionek z Google, żadnych CDN-ów, logo
rejestru leży w `static/logo_rspo.png`, a nie jest ciągnięte z ich serwera. Na
serwerze bez internetu narzędzie ma wyglądać tak samo. Ta sama zasada obowiązuje
w aplikacji leadów.

**Brak logowania — świadomie, dopóki narzędzie chodziło lokalnie.** Na publicznym
adresie ta decyzja przestaje obowiązywać i **nie da się jej po prostu przenieść**:
`/import` przyjmuje dowolny plik, `/rejony/usun/<id>` kasuje rejon,
a `/placowki/objete` przestawia flagę hurtem — wszystkie bezwarunkowo. Sam
rejestr jest publiczny, ale to, KTÓRE szkoły klient wziął na cel, już nie.

Na VPS-ie pilnuje tego **nginx Basic Auth** (`docs/WDROZENIE.md`, punkt 5) — bez
linijki kodu i bez czekania. To **plaster, nie rozwiązanie**: jedno hasło dla
wszystkich, bez wylogowania i bez śladu, kto co zrobił. Docelowo ten sam
mechanizm PIN-ów, co w aplikacji leadów; wtedy wpis `auth_basic` z nginx wypada.

**Brak automatu pobierającego plik.** Plik wgrywa człowiek. Automat na serwerze
umiera po cichu i nikt nie zauważy przez miesiąc — ta sama zasada, co przy
auto-zwrocie leadów w aplikacji obok.

---

## 6. Podpięcie do `leady_app_v5`

**Dziś — przez plik, bez ani jednej linijki nowego kodu po tamtej stronie:**

1. tutaj: Placówki → filtry → **↓ Wykaz do leadów**
2. tam: **↑ Import → źródło RSPO → tryb `dopisz`**

`eksport.NAGLOWKI_WYKAZU` to osiem kolumn dopasowanych do
`importer.NAGLOWKI_RSPO` w aplikacji leadów. **Sprawdzone end-to-end** (nie
tylko teoretycznie): 1 605 placówek weszło do czystej bazy leadów, ponowny
import tego samego pliku dołożył 0.

⚠️ **Format „pełny" NIE nadaje się do tamtego importu** — ma kolumny „Gmina"
i „Miejscowość", które tamten importer mapuje na to samo pole.

**Jutro — przycisk zamiast pliku.** `importer.importuj_rspo()` przyjmuje
**ścieżkę do pliku** i dopasowuje po numerze RSPO, więc przeniesienie jednym
kliknięciem nie wymaga żadnej nowej logiki importu — tylko transportu między
dwiema aplikacjami stojącymi na tym samym serwerze. Warianty, koszt i pytania
do klienta: `docs/POMYSL_przycisk_do_leadow.md`.

⚠️ **Dopasowywanie naszych starych rekordów do rejestru to NIE jest ten projekt.**
Robi to `..\leady_app_v5\narzedzia\rspo.py dopasuj` i tam zostaje — dotyczy bazy
leadów (10 par duplikatów, 16 nazw potocznych typu „Piasek", „EduHub"), nie
rejestru.

---

## 7. Grabie, na które już nadepnęliśmy

**Kolizja nazw modułów `db`.** Oba projekty mają `db.py`. Zaimportowanie
`leady_app_v5/importer.py` w procesie, który ma już nasze `db`, wysypuje się na
`ImportError: cannot import name 'alias_map' from 'db'`. Testy dotykające obu
projektów **muszą iść w osobnych procesach**.

**Polskie cudzysłowy `„…”` w stringach Pythona.** Zamykający ASCII `"` kończy
string i psuje składnię — `SyntaxError: invalid character '„'` wskazuje wtedy
mylące miejsce. Używać pary typograficznej `„…”` (U+201E i U+201D) albo
apostrofów. Kosztowało to już jeden przebieg poprawek w `rejony.py`.

**`curl` w Git Bashu psuje polskie znaki w danych formularza.** Gmina
„Gierałtowice" wylądowała w bazie jako `Giera%B3towice`. Do testowania POST-ów
z polskimi znakami używać Pythona (`urllib.parse.urlencode(..., encoding='utf-8')`),
nie curla.

**Flask w trybie debug to DWA procesy** (reloader + potomny). Zabicie po porcie
trafia w jeden i port zostaje zajęty. Działa:
```powershell
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
  Where-Object { $_.CommandLine -like '*app.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

**`request.form["x"]` przy braku pola daje 400/500.** Ekran rejonów ma jeden
endpoint na trzy warianty formularza — pomyłka w polu nie może wyglądać jak
awaria narzędzia. Używać `.get()` i wracać z komunikatem (`_int()` w `app.py`).

**Jinja nie obsługuje `{% macro foo(**kwargs) %}`.** Stąd helper `link()` jest
funkcją Pythona wystawioną przez `@app.template_global()`, a nie makrem.

**Konsola Windows to cp1250.** Skrypty CLI muszą robić
`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`, inaczej wywalają
się na własnym komunikacie ze strzałką „→".

**`pip` na tym komputerze celuje w innego Pythona niż `python`.** Instalować
przez `python -m pip install …`.

---

## 8. Konwencje

**Komentarze po polsku i wyjaśniają DLACZEGO, nie CO.** Kod mówi, co robi;
komentarz ma powiedzieć, jakiego realnego problemu klienta dotyczy. Odwołania do
konkretów („278 zespołów i 341 ich składowych to ten sam telefon") są dowodem,
nie ozdobą.

**Nazwy funkcji, zmiennych i tras po polsku** — projekt ma przejąć ktoś
z zespołu klienta.

**Testy to zwykły skrypt `.py`**, nie pytest: `sprawdz(nazwa, warunek, opis)`,
wypisuje `[OK]/[BLAD]` i podsumowanie `N/N`, działa na bazie w
`tempfile.mkdtemp()`. Baza testowa ma **40 placówek, nie trzy** — przy mniejszej
bezpiecznik zniknięć odpalałby się zawsze i test sprawdzałby, że mechanizm nie
działa.

**Bez bibliotek frontendowych i bez buildu.** Cały JS (`static/rspo.js`) to
delegowane nasłuchy na dokumencie, ~50 linii. Reszta chodzi na zwykłych
formularzach, bo formularz przeżywa odświeżenie, przycisk wstecz i wklejony
adres — a stan trzymany w przeglądarce nie przeżywa niczego z tych trzech.

**Wygląd:** tokeny `:root` w `static/style.css` są przepisane jeden do jednego
z `..\leady_app_v5\static\style.css` (paleta próbkowana z logo SILESIA 3D,
Segoe UI, promienie 6/10/14, gradientowe przyciski). Zmiana koloru marki to
zmiana w dwóch plikach — nie polowanie na `#22c2f2` po całym projekcie.

---

## 9. Stan na 11.08.2026 (wtorek rano)

**Działa i jest sprawdzone na realnym pliku. Testy 39/39.**

Baza w `dane/rspo.db` jest już wypełniona:

| | szt. |
|---|---|
| wierszy w pliku (cała Polska) | 56 190 |
| **województwo śląskie** w bazie | **6 116** |
| w rejonach (17 rejonów z listy Kasi) | 2 552 |
| **wykaz roboczy** (rejony × nasze typy) | **1 605** |
| uczniów w rejonach | 329 156 |

Rozbicie w rejonach: 733 przedszkola · 549 podstawówek · 278 zespołów szkół ·
552 ponadpodstawowe · 45 pozaszkolnych i kultury.

> **Liczba do wyjaśnienia, gdyby ktoś porównywał z analizą z 09.08:** tam wykaz
> miał **1 573**, tu **1 605**. Różnica to 32 placówki — grupa „Pozaszkolne
> i kultura" jest tutaj szersza niż w narzędziu CLI, które brało sam młodzieżowy
> dom kultury. Zawężenie to jedno kliknięcie w przełączniku „RODZAJ".
> Wszystkie pozostałe liczby zgadzają się co do sztuki z analizą.

### Co jest zrobione

- wgrywanie CSV/XLSX, odsiew do śląskiego, raport nowe/zmienione/zniknięte
- dziennik zmian pole po polu (tabela `zmiany`, widoczny na karcie placówki)
- rejony: 17 startowych, poszerzanie o powiat/gminę, białe plamy posortowane
  tak, że na górze jest to, co klient ma już w swoim słowniku
- filtry, flaga „objęta działaniem" (pojedynczo i hurtem na wyniku filtrów)
- eksport w dwóch formatach, link i logo prowadzące do `rspo.gov.pl/institutions`

### Co dalej (kolejność nie jest dowolna)

0. **Wdrożenie na `rspo.silesia3d.site`** — komplet plików gotowy (`Dockerfile`,
   `docker-compose.yml`, `wdroz.sh`, `nginx/`, `narzedzia/kopia.py`), instrukcja
   krok po kroku w **`docs/WDROZENIE.md`**. Do wykonania na serwerze; zaczyna się
   od rekordu `A` w OVH, bo DNS propaguje się najdłużej. **Baza idzie z lokalnej
   przez `scp`, nie przez `/import` na produkcji** — świeży import odtworzy
   placówki, ale nie flagi „objęta”, notatki ani poszerzone rejony.
1. **Mapa rejonów, etap 1 (~1 dzień)** — granice gmin z PRG
   (`geoportal.gov.pl`, GUGiK, dane publiczne; śląskie to 167 gmin), łączone
   z naszymi po **TERYT**, rysowane jako **SVG prosto z GeoJSON — bez kafelków
   i bez bibliotek z CDN-u**, więc działa też bez internetu. Klik w gminę →
   wpada do rejonu.
2. **Wysłać wniosek o API** — szkic w `tmp/wniosek-mail-szkic.md`, zegar 14 dni,
   nic nie blokuje. Brakuje danych rejestrowych SILESIA 3D i decyzji, kto
   podpisuje wzór z `tmp/zrodla/Wniosek.pdf`.
3. **`api.py` obok `plik.py` (~1 dzień, gdy przyjdą dane logowania).** Ma zwracać
   **taką samą listę słowników**, jaką dziś zwraca `plik.py` — wtedy wpada
   w istniejący `magazyn.wgraj()` i w rdzeniu nie zmienia się nic. Login i hasło
   z `os.environ` (`RSPO_API_LOGIN` / `RSPO_API_HASLO`), **nigdy w kodzie ani
   w repo**. Przycisk „Odśwież z rejestru" na ekranie *Wgraj plik*, z datą
   ostatniego odświeżenia — **nie cron**. Szczegóły i mapowanie pól:
   `tmp/API_RSPO_notatki.md`, sekcja 5.
4. **Przycisk „Przenieś do leadów" (~pół dnia)** — zamiast pobierz XLSX + wgraj
   ręcznie. **Da się tanio, bo trudna część jest już zrobiona:**
   `importer.importuj_rspo()` po tamtej stronie przyjmuje ścieżkę do pliku
   i dopasowuje po numerze RSPO (stąd 1 605 wgranych, 0 przy powtórce). Brakuje
   samego transportu — jeden endpoint w leadach, wspólny sekret w `.env` obu
   aplikacji, jeden przycisk u nas. Wysyłać ma **bieżące filtry**, nie całość.
   Pomysł, warianty i pytania do klienta: **`docs/POMYSL_przycisk_do_leadow.md`**.
5. **Mapa, etap 2 — pinezki placówek (~1 dzień + czas na współrzędne).** Wymaga
   `lat`/`lon`: z API (potwierdzone, patrz sekcja 4) albo z geokodowania adresów
   w Nominatim (limit 1 zapytanie/s → ~30 min dla wykazu, ~1,5 h dla całego
   śląskiego, jednorazowo, zapisane w bazie). Kolumny już są.
5. **Przeniesienie do aplikacji leadów jako ekran koordynatora** — wtedy plik
   przestaje wędrować między programami.

### Decyzje po stronie klienta — narzędzie obsługuje każdy wariant

- **Wojtek:** zakres bazy (1 605 / 2 552 / 6 116). Dziś w bazie jest całe
  śląskie, a filtr zawęża — rekomendacja: tak zostawić.
- **Kasia:** zespół szkół czy jego składowe? 278 zespołów i 341 składowych to ten
  sam adres i telefon; karta placówki pokazuje je jako „pozostałe człony zespołu",
  ale to Kasia wie, z kim umawia się DT.
- **Kasia:** 10 par zdublowanych szkół i 16 nazw potocznych — **temat bazy
  leadów**, nie tego narzędzia.
- **Kasia, do przycisku „Przenieś do leadów":** co ze szkołami, które już są
  w leadach? Dziś import je pomija po numerze RSPO — nie rusza statusu ani
  historii. Ale rejestr bywa świeższy (telefon, dyrektor, nazwa). Pomijać /
  uzupełniać puste pola / pokazywać różnice do zatwierdzenia. Pełna lista pytań
  na spotkanie: `docs/POMYSL_przycisk_do_leadow.md`.

---

## 10. Materiały źródłowe

| Co | Gdzie |
|---|---|
| **Wdrożenie na VPS** krok po kroku (DNS, nginx, hasło, certbot, kopie) | `docs\WDROZENIE.md` |
| **Przycisk „Przenieś do leadów"** — pomysł, warianty, pytania do klienta | `docs\POMYSL_przycisk_do_leadow.md` |
| Wzór bloku nginx (kopiowany na serwer wprost z repozytorium) | `nginx\rspo.silesia3d.site.conf` |
| Wdrożenie aplikacji leadów — szerszy opis tej samej ścieżki | `..\leady_app_v5\docs\15_DOMENA_I_WDROZENIE.md` |
| **Ustalenia o API** (pola, filtry, regulamin, limity, plan wdrożenia) | `tmp\API_RSPO_notatki.md` — **czytać przed pracą nad API** |
| Oficjalne pliki CIE: OpenAPI, instrukcja, regulamin, wzór wniosku | `tmp\zrodla\` |
| Szkic maila z wnioskiem o dostęp | `tmp\wniosek-mail-szkic.md` |
| Prezentacja o API (dla klienta) | `tmp\prezentacja-api\index.html` |
| Analiza „RSPO — status i plan", 09.08 | `..\leady_app_v5\tmp\analizy\analiza_rspo\index.html` |
| Analiza „rejestr kontra nasza baza" (pokrycie rejonów, białe plamy) | `…\analiza_rspo\porownanie.html` |
| Propozycja rozwiązania dla klienta | `..\leady_app_v5\docs\12_RSPO.md` |
| Narzędzie CLI (poprzednik, nadal używane do `dopasuj`) | `..\leady_app_v5\narzedzia\rspo.py` |
| Plik wzorcowy z rejestru | `..\8.08.2026-home\plik rspo\rspo_2026_08_08.csv` |
| Kontekst aplikacji leadów | `..\leady_app_v5\CLAUDE.md` |
