# Pomysł: „Przenieś do leadów" jednym przyciskiem

Spisane 11.08.2026, **przed** spotkaniem prezentacyjnym u klienta — po to, żeby
pytania do Kasi i Wojtka nie były wymyślane na miejscu. To notatka planistyczna,
nie specyfikacja: decyzje po spotkaniu dopisujemy tutaj.

## Skąd pytanie

Dzisiejsza ścieżka ma cztery ruchy człowieka: w RSPO ustaw rejony → sprawdź dane
→ pobierz XLSX → w leadach wgraj plik. Trzy pierwsze to praca merytoryczna,
czwarty jest przenoszeniem pliku między dwoma programami na tym samym serwerze.

## Krótka odpowiedź: da się, i to taniej, niż wygląda

**Trudna część jest już zrobiona i sprawdzona end-to-end.** Po stronie leadów
`importer.importuj_rspo(conn, sciezka)` przyjmuje **ścieżkę do pliku** i zwraca
raport (`placowki`, `leady`, `pominiete`, `uwagi`). Dopasowuje po **numerze
RSPO** (`_klucz_placowki` → `("rspo", numer)`), dlatego ponowny import tego
samego wykazu dołożył **0** rekordów przy 1 605 wgranych za pierwszym razem.

Znaczy to, że przycisk **nie potrzebuje ani jednej nowej linijki logiki
importu**. Brakuje wyłącznie transportu: jak plik ma przejść z jednej aplikacji
do drugiej bez człowieka pośrodku.

## Trzy poziomy — rosnący koszt, malejąca liczba ruchów

**1. Dziś: plik i człowiek.** Działa, nic nie wymaga. Zostaje na stałe jako
wyjście awaryjne — gdy leady nie odpowiadają, wykaz i tak da się pobrać.

**2. Przycisk (~pół dnia).** Obie aplikacje stoją na tym samym VPS-ie. RSPO
buduje ten sam XLSX co dziś i podaje go leadom po HTTP; leady wołają swoją
istniejącą funkcję i oddają raport, który RSPO pokazuje na ekranie.
Nowe: **jeden endpoint po stronie leadów + wspólny sekret w `.env` obu aplikacji
+ jeden przycisk u nas.** Nic więcej.

**3. Docelowo: jedna baza.** RSPO wchodzi do aplikacji leadów jako ekran
koordynatora (etap 5 z CLAUDE.md §9) i plik przestaje istnieć — „przenieś"
zamienia się w „oznacz". Poziom 2 nie jest wtedy wyrzucany, tylko przestaje być
potrzebny; te same pytania trzeba rozstrzygnąć tak czy owak.

## Co przycisk ma wysyłać — i to jest właściwe pytanie

**Dokładnie to, co koordynatorka ma na ekranie**, czyli bieżące filtry — te same
`zapytania._warunki()`, z których korzysta eksport. Przycisk „wyślij wszystko"
byłby wygodniejszy do napisania i gorszy w użyciu: sens tego narzędzia polega na
tym, że najpierw się zawęża, a potem przenosi.

Podpis pod przyciskiem ma mówić liczbę **przed** kliknięciem („przeniesie 1 605
placówek z 6 116"), a nie po.

## Pytania do klienta — na dzisiejsze spotkanie

**1. Co ze szkołami, które są już w leadach?** Dziś import je **pomija** po
numerze RSPO — nie rusza ani statusu, ani historii kontaktów. Ale rejestr bywa
świeższy: szkoła zmienia telefon, dyrektora, nazwę. Trzy warianty do wyboru:
pomijać (dziś), dopisywać tylko puste pola (tak działa import w leadach dla
pozostałych źródeł), albo pokazywać listę różnic do zatwierdzenia. **To decyzja
Kasi, nie nasza** — dotyczy danych, na których pracuje.

**2. Czy przycisk wysyła od razu, czy pokazuje podgląd?** Zapis do bazy
sprzedażowej jest jednokierunkowy — cofnąć się da tylko z kopii. Podgląd
(„dopiszę 132 nowe, 1 473 już są, 0 z konfliktem") kosztuje jedno kliknięcie
więcej i zdejmuje całą klasę pomyłek.

**3. Kto ma prawo kliknąć?** Dziś RSPO nie ma logowania — na serwerze pilnuje
tego hasło w nginx, jedno dla wszystkich. Przycisk zapisujący do bazy
handlowców to moment, w którym „kto to zrobił" zaczyna mieć znaczenie i wraca
temat PIN-ów z aplikacji leadów.

**4. Co z 278 zespołami szkół i 341 ich składowymi?** Pytanie stare (CLAUDE.md
§9), ale przycisk je zaostrza: dziś człowiek widzi wykaz w Excelu przed
wgraniem i może coś skreślić. Po kliknięciu nie ma tego momentu.

## Grabie, o których będzie wiadomo dopiero przy pisaniu

- **Kontener nie widzi `127.0.0.1` hosta.** Obie aplikacje są w dockerze, więc
  „przecież to ta sama maszyna" nie wystarczy — trzeba wspólnej sieci docker
  albo wpisu `extra_hosts`. Pierwsza próba na pewno skończy się „connection
  refused" i wnioskiem, że coś jest nie tak z endpointem.
- **Kolizja nazw modułów `db`** (CLAUDE.md §7) wyklucza wołanie `importer.py`
  wprost z naszego procesu. To akurat argument ZA rozwiązaniem po HTTP: dwa
  osobne procesy nie mają tego problemu z definicji.
- **Format „wykaz", nie „pełny".** Ten drugi ma kolumny „Gmina" i „Miejscowość",
  które tamten importer mapuje na to samo pole. Przycisk musi mieć format
  zaszyty na sztywno — wybór formatu przy takim przycisku to pułapka.
- **`replace=True` czyści tylko nieprzydzielone leady** (`wyczysc(conn,
  tylko_nieprzydzielone=True)`) — przydzielone z historią przeżywają. Dobrze
  o tym wiedzieć, zanim ktoś zaproponuje „a może guzik do wyczyszczenia".

## Czego ten przycisk NIE załatwia

Dopasowania naszych starych rekordów do rejestru — 10 par duplikatów i 16 nazw
potocznych („Piasek", „EduHub") w bazie leadów. Robi to
`..\leady_app_v5\narzedzia\rspo.py dopasuj` i to zostaje osobną robotą: dotyczy
bazy leadów, nie rejestru, i wymaga człowieka przy każdej parze.
