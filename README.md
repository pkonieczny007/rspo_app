# RSPO — narzędzie do zarządzania bazą placówek

Osobna aplikacja Flask obok `leady_app_v5`. Wgrywasz plik z rejestru, widzisz
wszystkie placówki, ustawiasz i poszerzasz rejony, wyprowadzasz wykaz, który
łyka aplikacja leadów.

**Stan na 11.08.2026:** działa, przetestowane na realnym pliku
(`rspo_2026_08_08.csv`, 56 190 wierszy). 39/39 sprawdzeń w `test_rspo.py`.

---

## Uruchomienie

```powershell
cd C:\XEN\AI-szkolenie\SIERPIEN2026\rspo_app
python -m pip install -r requirements.txt
python app.py
```

→ http://127.0.0.1:5310  (port 5301 zajmuje aplikacja leadów)

Baza siada w `dane/rspo.db`. Inny katalog: `$env:RSPO_DATA="D:\gdzies"`.
Testy: `python test_rspo.py`.

---

## Cztery ekrany

| Ekran | Co robi |
|---|---|
| **Pulpit** | ile mamy, ile w rejonach, ile poza, rozbicie na rodzaje placówek, historia wgrań |
| **Placówki** | lista z filtrami: szukajka, rejon, powiat, typ, publiczność, rodzaj (przedszkola / podstawówki / zespoły…), stan (czynne / zniknęły z rejestru). Eksport tego, co widać |
| **Rejony** | nasze rejony, ich obszary, poszerzanie o powiat albo gminę, **białe plamy** — powiaty spoza rejonów posortowane wg tego, ile placówek by doszło |
| **Wgraj plik** | link prosto do rejestru (**rspo.gov.pl/institutions**) + wgranie pliku → raport: co nowe, co się zmieniło, co zniknęło + dziennik zmian pole po polu |

---

## Jak to działa — trzy decyzje, na których stoi całość

**1. Numer RSPO jest kluczem głównym tabeli.**
Nie `id`, nie nazwa. Szkoły zmieniają nazwy („SP nr 12" → „SP nr 12 im. Jana
Pawła II"), adresy i dyrektorów; stały jest tylko numer. Dzięki temu „kolejne
wgranie dogrywa nowe, ale nie robi duplikatów" nie jest starannością w kodzie,
którą da się przeoczyć przy następnej poprawce — jest warunkiem narzuconym
przez bazę. *Sprawdzone: to samo 6116 rekordów wgrane dwa razy → 6116 w bazie,
0 nowych, 0 zmienionych.*

**2. Rejon to lista obszarów, nie kolumna na placówce.**
`rejon_obszary` trzyma pary (powiat|gmina, nazwa), a `placowka_rejon` jest
przeliczane po każdej zmianie. Poszerzenie terenu to dopisanie jednej linijki
i ułamek sekundy, a nie przepisanie tysiąca wierszy. **Gmina bije powiat**:
Knurów zostaje przy swoim rejonie, nawet gdy cały powiat gliwicki trafi kiedyś
do „Gliwic".

**3. Baza jest lustrem rejestru — z jednym wyjątkiem.**
Rejestr nadpisuje swoje pola (inaczej po pół roku nie wiadomo, co jest aktualne,
a co naszym starym odbiciem). Import **nigdy** nie dotyka trzech naszych kolumn:
`objeta` („objęta działaniem"), `notatka` i `pierwszy_import`.

Placówki, których zabrakło w pliku, **oznaczamy, nie kasujemy** — mogły się
przekształcić albo połączyć, a w aplikacji leadów wisi na nich historia
kontaktów. Bezpiecznik: gdyby ktoś wgrał plik przefiltrowany w wyszukiwarce
(np. same Katowice), naiwne porównanie oznaczyłoby resztę województwa jako
zniknięcie — więc oznaczamy tylko wtedy, gdy ubytek jest mały bezwzględnie
(≤25) **i** względnie (≤20% bazy). Inaczej narzędzie nie robi nic i mówi dlaczego.

---

## Podpięcie do aplikacji leadów

**Dziś — przez plik, bez ani jednej linijki nowego kodu po tamtej stronie:**

1. tutaj: Placówki → ustaw filtry → **↓ Wykaz do leadów**
2. tam: **↑ Import → źródło RSPO → tryb `dopisz`**

Wykaz ma osiem kolumn dokładnie w formacie, który rozpoznaje
`importer.NAGLOWKI_RSPO`. *Sprawdzone end-to-end: 1605 placówek weszło do
czystej bazy leadów, ponowny import tego samego pliku dołożył 0.*

**Docelowo:** ten sam kod wchodzi do aplikacji leadów jako ekran koordynatora
i plik przestaje wędrować między programami. Nic z dzisiejszej struktury nie
stoi temu na drodze — `magazyn.py`, `rejony.py` i `zapytania.py` nie wiedzą
nic o Flasku.

---

## Liczby z realnego pliku (`rspo_2026_08_08.csv`)

| | szt. |
|---|---|
| wierszy w pliku (cała Polska) | 56 190 |
| **województwo śląskie** (wchodzi do bazy) | **6 116** |
| w naszych rejonach (17 rejonów z listy Kasi) | 2 552 |
| **wykaz roboczy** — rejony × nasze typy | **1 605** |
| uczniów w rejonach | 329 156 |

W rejonach: 733 przedszkola · 549 podstawówek · 278 zespołów szkół ·
552 ponadpodstawowe · 45 pozaszkolnych i kultury.

> Wykaz roboczy pokazuje 1 605, a analiza z 09.08 mówiła 1 573. Różnica to
> 32 placówki z grupy „Pozaszkolne i kultura": narzędzie z linii poleceń brało
> sam młodzieżowy dom kultury, tutaj grupa obejmuje też ogniska pracy
> pozaszkolnej, międzyszkolne ośrodki sportowe, pałac młodzieży i niepubliczne
> placówki oświatowo-wychowawcze. Zawężenie to jedno kliknięcie w przełączniku
> „RODZAJ".

---

## Filtry po rodzaju — dlaczego grupy, a nie lista typów

Rejestr ma w samym śląskim **43 różne typy** placówek. Lista rozwijana z 43
pozycjami to spis treści, nie filtr. Dlatego obok pełnej listy (bo czasem
trzeba precyzyjnie) jest osiem grup rozpoznawanych **po słowach kluczowych**:
gdy rejestr doda „Przedszkole integracyjne", wpadnie do przedszkoli samo,
zamiast wylądować w „innych" i zniknąć koordynatorce z oczu.

„Nasze typy" = przedszkola + podstawówki + zespoły + pozaszkolne i kultura.
Reszta zostaje w bazie (Wojtek ma pełny zasięg), ale nie zaśmieca wykazu.

---

## Mapa — odpowiedź na pytanie z 11.08

**Krótko: tak, ale nie z tego pliku i nie w jeden dzień. Da się rozbić na dwa
etapy, z których pierwszy jest tani i załatwia większość tego, o co chodzi.**

### Czego w pliku RSPO nie ma

Sprawdzone kolumna po kolumnie: **54 kolumny i ani jednej ze współrzędnymi.**
Jest za to `Kod terytorialny gmina` (TERYT) — i to jest klucz do mapy rejonów.
W naszej bazie TERYT ma **6 116 z 6 116** placówek, czyli 100%.

### Etap 1 — mapa rejonów (~1 dzień) — to jest to, o co realnie chodzi

Malujemy **granice gmin** wypełnione kolorem rejonu, z liczbą placówek
w środku. Klikasz gminę → dopisuje się do rejonu (to samo, co dziś robi
przycisk „+ poszerz", tylko widać, gdzie to jest).

- granice: **PRG z geoportal.gov.pl** (GUGiK, dane publiczne, za darmo),
  województwo śląskie to 167 gmin — po uproszczeniu geometrii kilkaset kB
- łączenie z naszymi danymi: **po TERYT**, bez żadnego geokodowania
- rysowanie: **SVG prosto z GeoJSON, bez kafelków i bez bibliotek z CDN-u** —
  ta sama zasada, co w aplikacji leadów: nic nie pobieramy z internetu, więc
  narzędzie wygląda tak samo na serwerze bez dostępu do sieci
- ryzyko: żadne. Granice gmin zmieniają się raz na kilka lat

### Etap 2 — pinezki poszczególnych placówek (~1 dzień + czas na współrzędne)

Tu potrzeba szerokości i długości geograficznej, których w pliku nie ma.
Dwa źródła, oba do zrobienia:

| Źródło | Koszt | Uwagi |
|---|---|---|
| **API rejestru** (`api.rspo.gov.pl`) | wniosek + do 14 dni, dostęp bezpłatny | **potwierdzone w oficjalnej specyfikacji** (`tmp/zrodla/api-docs.yaml`): `geolokalizacja[] → {latitude, longitude}`. To jest ta jedna rzecz, dla której warto składać wniosek |
| **Geokodowanie adresów** (Nominatim/OSM) | jednorazowo ~30 min dla wykazu, ~1,5 h dla całego śląskiego | limit 1 zapytanie/s; wynik zapisujemy raz w bazie i już nigdy nie pytamy ponownie |

Kolumny `lat` i `lon` **są już w schemacie bazy** — puste, czekają. Nie trzeba
niczego przebudowywać, gdy współrzędne przyjdą.

**Rekomendacja:** etap 1 po wtorku, razem z resztą prac nad RSPO. Etap 2 —
gdy przyjdzie odpowiedź w sprawie API, bo wtedy jest za darmo i dokładniejszy
niż geokodowanie adresów.

---

## Rytm pracy

Raz w miesiącu (koordynator, ok. 10 minut):

1. **https://rspo.gov.pl/institutions** → „Pobierz wyniki" → CSV
   *(przycisk „Otwórz rspo.gov.pl ↗" jest na ekranie „Wgraj plik" i na pustym
   pulpicie — nie trzeba pamiętać adresu. Logo rejestru leży u nas
   w `static/logo_rspo.png`, nie jest ciągnięte z ich serwera, więc ekran
   wygląda tak samo bez internetu.)*
2. tutaj: **Wgraj plik** → raport pokazuje, co doszło i co się zmieniło
3. **Rejony** → sprawdź, czy w białych plamach nie urosło coś, co nas obchodzi
4. **Placówki** → filtry → **↓ Wykaz do leadów**
5. w aplikacji leadów: **↑ Import → RSPO → dopisz**

Szkoły nie zmieniają się z dnia na dzień — miesiąc jest w sam raz.

---

## Pliki

| Plik | Za co odpowiada |
|---|---|
| `app.py` | trasy Flaska, nic poza sklejaniem |
| `db.py` | schemat, mapa 34 kolumn rejestru, grupy typów |
| `plik.py` | czytanie CSV/XLSX z rspo.gov.pl (kodowanie, „pancerz Excela" `="0123"`) |
| `magazyn.py` | wgrywanie do bazy — nowe / zmienione / zniknięte, dziennik zmian |
| `rejony.py` | rejony, obszary, przeliczanie, białe plamy |
| `zapytania.py` | filtry listy i liczniki pulpitu — jedno miejsce dla ekranu i eksportu |
| `eksport.py` | XLSX: „wykaz" (8 kolumn pod aplikację leadów) i „pełny" |
| `test_rspo.py` | 39 sprawdzeń na pliku wzorcowym i bazie tymczasowej |

Wgrane pliki zostają w `dane/wgrane/` ze znacznikiem czasu — żeby dało się
wrócić do **tego** pliku, gdy raport pokaże coś dziwnego.

---

## Czego tu świadomie nie ma

- **logowania** — narzędzie chodzi lokalnie u koordynatora; gdy wejdzie na VPS,
  dostanie ten sam mechanizm PIN-ów, co aplikacja leadów
- **dopasowywania naszych starych rekordów do rejestru** — to robi
  `leady_app_v5/narzedzia/rspo.py dopasuj` i tam zostaje: dotyczy bazy leadów,
  nie rejestru
- **kasowania czegokolwiek** — placówki się oznacza, nie usuwa
- **automatycznego pobierania z rspo.gov.pl** — plik wgrywa człowiek, świadomie.
  Automat na serwerze umiera po cichu i nikt nie zauważy przez miesiąc
