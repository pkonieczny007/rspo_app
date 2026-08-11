# API RSPO — co ustaliliśmy z dokumentów źródłowych (11.08.2026)

Wszystko poniżej pochodzi z **oficjalnych plików CIE**, pobranych 11.08.2026 do
`tmp/zrodla/`. To nie są domysły z dokumentacji sprzed tygodnia — to specyfikacja,
którą wystawia serwer.

| Plik w `tmp/zrodla/` | Skąd | Co z niego mamy |
|---|---|---|
| `api-docs.yaml` (34 kB) | `https://api.rspo.gov.pl/v3/api-docs.yaml` | OpenAPI 3.1.0, wersja API **1.2.0** — endpointy, filtry, pełna lista pól placówki |
| `RSPO-API-doc.pdf` (227 kB) | `https://api.rspo.gov.pl/files/RSPO-API-doc.pdf` | instrukcja (eksport kolekcji Postmana) — potwierdza Basic Auth i parametry |
| `Regulamin.pdf` (93 kB) | `https://api.rspo.gov.pl/files/Regulamin.pdf` | zasady, obowiązki, limity, cofnięcie dostępu; wchodzi w życie 14.01.2026 |
| `Wniosek.pdf` (91 kB) | `https://api.rspo.gov.pl/files/Wniosek.pdf` | **oficjalny wzór wniosku** — 5 sekcji do wypełnienia |

Strony: `https://api.rspo.gov.pl/`, `https://cie.gov.pl/nowe-api-wyszukiwarki-rspo/`.

---

## 1. Stan formalny

- Nowe API wyszukiwarki RSPO działa **od 15.01.2026**; poprzednia wersja
  (`api-rspo.men.gov.pl`) **została wyłączona 02.03.2026** — dziś ta domena
  nawet się nie rozwiązuje (sprawdzone). Kto pisał integrację na starym API,
  ma ją martwą.
- **Dostęp jest bezpłatny** i przyznawany **na czas nieokreślony** (Regulamin §1.5, §2.5).
- Wniosek mailem na **`rspo@cie.gov.pl`**, temat: *„Wniosek o dostęp do API [nazwa podmiotu]"*.
- **Rozpatrzenie do 14 dni.** Pozytywne rozpatrzenie = przyznanie
  **indywidualnych danych uwierzytelniających** (login + hasło, nie klucz API).
- CIE **może wprowadzić limity liczby zapytań** (§3.5) — dziś żadnego limitu
  liczbowego w dokumentach nie ma.
- CIE może **zawiesić lub cofnąć dostęp** (§5) i nie odpowiada za niedostępność
  ani za niezgodność danych ze stanem rzeczywistym (§4). Wniosek dla nas:
  API jest **dodatkiem**, a nie jedyną drogą do danych — ścieżka z plikiem CSV
  musi zostać działająca.
- Zakaz przekazywania danych uwierzytelniających osobom trzecim i używania API
  „do celów niezgodnych z wnioskiem" — czyli **opis wykorzystania we wniosku
  wyznacza granicę**, w której wolno nam się potem poruszać. Warto go napisać
  szeroko (baza placówek + kontakt handlowy + rejonizacja), nie wąsko.

## 2. Jak to działa technicznie

- **REST + JSON**, uwierzytelnianie **HTTP Basic Auth** (`basicAuth` w spec).
- Serwer podany w specyfikacji to `http://api.rspo.gov.pl` (bez S) — **łączymy się
  wyłącznie po `https://`**. Basic Auth po czystym HTTP to wysyłanie hasła
  otwartym tekstem przy każdym zapytaniu.
- Główny zasób: **`GET /api/placowki/`** (kolekcja) i `GET /api/placowki/{id}`.
- Paginacja: `page` + `pageSize`, **domyślnie 100 na stronę**.
  Odpowiedź to goła tablica JSON — **nie ma pola z liczbą wszystkich wyników**,
  więc stronicujemy do pierwszej niepełnej strony.
- Poza placówkami 11 słowników do podpięcia list wyboru:
  `/api/typ/`, `/api/status_publiczno_prawny/`, `/api/kategoria_ucznia/`,
  `/api/etap_edukacyjny/`, `/api/specyfika_szkoly/`, `/api/zwiazanie_organizacyjne/`,
  `/api/wojewodztwa/`, `/api/powiaty/`, `/api/gminy/`, `/api/gminy_rodzaje/`,
  `/api/miejscowosci/`.

### Filtry na `/api/placowki/`

`wojewodztwo_nazwa`, `wojewodztwo_kod_teryt`, `powiat_nazwa`, `powiat_kod_teryt`,
`gmina_nazwa`, `gmina_kod_teryt`, `miejscowosc_nazwa`, `miejscowosc_kod_teryt`,
`RSPO`, `NIP`, `REGON`, `typ_podmiotu_id`, `status_publiczno_prawny_id`,
`kategoria_ucznia_id`, `etap_edukacji_id`, `zlikwidowana`, `podmiot_prowadzacy_id`,
`podmiot_prowadzacy_regon`, `page`, `pageSize`.

**Czego wśród filtrów NIE MA (to jest ważne dla nas):**
- **nie ma filtra „zmienione od daty"** → każde odświeżenie to pobranie całości
  i porównanie po naszej stronie. Nasz `magazyn.py` już dokładnie to robi;
- **nie ma szukania po fragmencie nazwy placówki** (`RSPO`, `NIP`, `REGON` są
  „full number") → dopasowywanie nazw potocznych („MSP 1", „Piasek") zostaje
  po naszej stronie, API tu nie pomoże.

## 3. Pola placówki (`PlacowkaDTO`) kontra nasze 34 kolumny z pliku CSV

### Mamy jedno w drugim (mapowanie 1:1 albo prawie)

| Nasza kolumna (`db.py`) | Pole API | Uwaga |
|---|---|---|
| `rspo` | `numerRspo` | klucz, bez zmian |
| `nazwa`, `regon`, `nip`, `liczba_uczniow` | `nazwa`, `regon`, `nip`, `liczbaUczniow` | |
| `typ` | `typ.nazwa` | obiekt, nie tekst |
| `dyrektor` | `dyrektorImie` + `dyrektorNazwisko` | **rozbity — lepiej niż w pliku** |
| `wojewodztwo`/`powiat`/`gmina`/`miejscowosc` | te same nazwy | |
| `teryt_gmina` | `gminaKodTERYT` | plus TERYT województwa, powiatu, miejscowości i **ulicy** |
| `ulica`, `nr_budynku`, `nr_lokalu`, `kod_pocztowy`, `poczta` | `ulica`, `numerBudynku`, `numerLokalu`, `kodPocztowy`, `poczta` | |
| `telefon`, `email`, `www` | `telefon`, `email`, `stronaInternetowa` | |
| `publicznosc` | `statusPublicznoPrawny` | obiekt |
| `kategoria_uczniow`, `specyfika` | `kategoriaUczniow`, `specyfikaSzkoly` | obiekty |
| `organ_typ`, `organ_nazwa`, `organ_regon` | `podmiotProwadzacy[]` | **tablica** — placówka może mieć kilka organów |
| `miejsce_w_strukturze` | `zwiazanieOrganizacyjne` | |
| `rspo_nadrzedny`, `nazwa_nadrzedna` | `podmiotNadrzedny` (tekst) | + `placowkiPodrzedne` |
| `data_zalozenia`, `data_likwidacji` | `dataZalozenia`, `dataLikwidacji` | ISO date-time zamiast tekstu |

### API daje więcej niż plik

- **`geolokalizacja[]` → `{latitude, longitude}`** — to jest ta jedna rzecz,
  dla której warto składać wniosek. Kolumny `lat`/`lon` czekają puste w schemacie.
- `liczbaOddzialow` — ile klas, obok liczby uczniów.
- `etapyEdukacji[]` — filtr twardszy niż zgadywanie po nazwie typu.
- `czyPosiadaObwod`, `czyPosiadaInternat`, `czyDotacjaWPrzyszlymRoku`.
- `rodzajSzkolyPlacowki`, `dataRozpoczecia`, `dataWlaczeniaDoZespolu`.
- `adresDoKorespondecji*` (6 pól) — inny adres do pism niż adres placówki.
- `podmiotPrzekazujacyDaneDoRSPO`, `ksztalcenieZawodowe[]` i dwa pokrewne.

### Plik daje coś, czego w API NIE MA

- **`faks`** — w `PlacowkaDTO` nie występuje w ogóle.
- **`jezyki` (Języki nauczane)** — nie występuje w ogóle.
- **`rodzaj_miejscowosci`** — nie ma na placówce; jest dopiero w
  `/api/miejscowosci/` jako `rodzajMiejscowosci`, do dociągnięcia po
  `miejscowoscKodTERYT` (167 gmin / kilka tysięcy miejscowości — jedno pobranie
  słownika, nie zapytanie na placówkę).

Praktycznie: przy imporcie z API te trzy kolumny zostawiamy **niezmienione**
(a nie czyścimy!), bo API po prostu o nich nie mówi. To jeden wyjątek od zasady
„rejestr nadpisuje swoje pola".

## 4. Ile to zapytań miesięcznie (do wpisania we wniosku)

Śląskie to 6 116 placówek. Przy `pageSize=100` pełne odświeżenie = **62 zapytania**;
przy `pageSize=1000` = **7**. Doliczając 11 słowników i zapas na ponowienia:
**realnie 100–200 zapytań na jedno odświeżenie, raz w miesiącu.**
We wniosku deklarujemy bezpiecznie: **do 2 000 zapytań miesięcznie**.

## 5. Co to zmienia w `rspo_app`

**W rdzeniu nic.** `db.py` (klucz RSPO), `magazyn.py` (nowe / zmienione /
zniknięte + dziennik zmian + bezpiecznik ubytku), `rejony.py` (TERYT), `eksport.py`
działają tak samo — zmienia się tylko to, skąd biorą wiersze.

Do zrobienia, gdy przyjdą dane logowania (~1 dzień):

1. `api.py` obok `plik.py` — pobiera stronicowaną kolekcję, spłaszcza obiekty
   i tablice do naszych 34 kolumn, dokłada `lat`/`lon`. Wynik: **taka sama lista
   słowników**, jaką dziś zwraca `plik.py` → wpada w istniejący `magazyn.wgraj`.
2. Login i hasło z `os.environ` (`RSPO_API_LOGIN` / `RSPO_API_HASLO`) — nigdy
   w kodzie ani w repo.
3. Przycisk **„Odśwież z rejestru"** na ekranie *Wgraj plik*, obok wgrywania
   pliku, z datą ostatniego odświeżenia. **Nie cron** — automat na serwerze
   umiera po cichu (ta sama zasada, co przy auto-zwrocie leadów).
4. Ścieżka z plikiem CSV **zostaje na stałe** — to jest nasze wyjście awaryjne
   na wypadek §4 i §5 regulaminu (zawieszenie, cofnięcie, niedostępność).

## 6. Stan wniosku na 11.08.2026

Wniosek **nie został jeszcze wysłany** i nie ma nigdzie napisanej treści maila —
w dokumentach (`docs/12_RSPO.md`, `docs/11_PLAN_v5.md`, analiza z 09.08) jest tylko
zadanie „wysłać wniosek, zegar 14 dni" i lista tego, co ma zawierać.
Szkic gotowy do wysłania: `tmp/wniosek-mail-szkic.md`.
Brakuje wyłącznie danych rejestrowych SILESIA 3D (adres, NIP/REGON) i decyzji,
kto podpisuje wzór z `Wniosek.pdf`.
