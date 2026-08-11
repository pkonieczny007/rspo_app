# -*- coding: utf-8 -*-
"""
Baza narzędzia RSPO — SQLite, bez ORM (tak jak w `leady_app_v5`, żeby ktoś, kto
przejmie oba projekty, czytał ten sam rodzaj kodu).

CZYM TA BAZA JEST, A CZYM NIE JEST
To LUSTRO REJESTRU, nie baza sprzedażowa. Jeden wiersz = jedna placówka
w Rejestrze Szkół i Placówek Oświatowych. Nie ma tu leadów, statusów ani
historii kontaktów — te zostają w `leady_app_v5`. Tutaj trzymamy to, co
przychodzi z rejestru, plus trzy własne rzeczy: przypisanie do rejonu, flagę
„objęta działaniem" i notatkę.

DLACZEGO `rspo` JEST KLUCZEM GŁÓWNYM, A NIE `id`
Szkoły zmieniają nazwy („SP nr 12" → „SP nr 12 im. Jana Pawła II"), przenoszą
się pod inny adres i zmieniają dyrektora. Stały jest tylko numer RSPO. Gdyby
tożsamość niósł tekst nazwy, każde kolejne wgranie pliku dokładałoby nowy wiersz
obok starego — czyli dokładnie to, przed czym całe narzędzie ma chronić.
`rspo INTEGER PRIMARY KEY` załatwia „bez duplikatów" na poziomie bazy, a nie
dobrych chęci w kodzie.

DLACZEGO REJESTR NADPISUJE NASZE POLA (inaczej niż w `leady_app_v5`)
W aplikacji leadów import uzupełnia tylko puste pola, bo handlowiec mógł poprawić
telefon ręcznie i jego poprawka jest cenniejsza. Tutaj jest odwrotnie: to lustro
rejestru, więc rejestr wygrywa — inaczej po pół roku nie wiedzielibyśmy, które
dane są aktualne, a które to nasze stare odbicie. Nasze trzy kolumny
(`rejon`, `objeta`, `notatka`) import nie rusza nigdy.
"""
import datetime as dt
import os
import sqlite3

KATALOG = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("RSPO_DATA") or os.path.join(KATALOG, "dane")
DB_PATH = os.environ.get("RSPO_DB") or os.path.join(DATA_DIR, "rspo.db")

WOJEWODZTWO_DOMYSLNE = "ŚLĄSKIE"

# ---------------------------------------------------------------------------
# POLA Z REJESTRU — jedno źródło prawdy dla schematu, importu, listy i eksportu.
#
# (kolumna w bazie, nagłówek w pliku z rspo.gov.pl, typ, etykieta na ekranie)
#
# Plik z wyszukiwarki RSPO ma 54 kolumny. Bierzemy 34 — te, które opisują
# placówkę i sposób dotarcia do niej. Odpuszczamy kolumny czysto oświatowe
# (zawody, oddziały, dziedzina BCU, tereny sportowe), bo nikt u nas nie
# podejmie na ich podstawie żadnej decyzji, a rozdymają tabelę.
#
# Dwie kolumny są tu ŚWIADOMIE, choć aplikacja leadów ich dziś nie przyjmuje:
#   liczba_uczniow  — daje kolejność obdzwaniania (szkoła na 600 uczniów to inny
#                     potencjał niż punkt przedszkolny na 12); dziś handlowiec
#                     dzwoni alfabetycznie
#   organ_nazwa     — 6 na 10 przedszkoli w naszych rejonach prowadzi ten sam
#                     organ, co szkoła, którą już mamy; to nie jest zimny telefon
# ---------------------------------------------------------------------------

POLA_RSPO = [
    ("rspo",                "Numer RSPO",                   "int",  "Nr RSPO"),
    ("nazwa",               "Nazwa",                        "text", "Nazwa"),
    ("typ",                 "Typ",                          "text", "Typ"),
    ("regon",               "REGON",                        "text", "REGON"),
    ("nip",                 "NIP",                          "text", "NIP"),

    ("wojewodztwo",         "Województwo",                  "text", "Województwo"),
    ("powiat",              "Powiat",                       "text", "Powiat"),
    ("gmina",               "Gmina",                        "text", "Gmina"),
    ("miejscowosc",         "Miejscowość",                  "text", "Miejscowość"),
    ("rodzaj_miejscowosci", "Rodzaj miejscowości",          "text", "Rodzaj miejscowości"),
    ("teryt_gmina",         "Kod terytorialny gmina",       "text", "TERYT gminy"),

    ("ulica",               "Ulica",                        "text", "Ulica"),
    ("nr_budynku",          "Numer budynku",                "text", "Nr budynku"),
    ("nr_lokalu",           "Numer lokalu",                 "text", "Nr lokalu"),
    ("kod_pocztowy",        "Kod pocztowy",                 "text", "Kod pocztowy"),
    ("poczta",              "Poczta",                       "text", "Poczta"),

    ("telefon",             "Telefon",                      "text", "Telefon"),
    ("faks",                "Faks",                         "text", "Faks"),
    ("email",               "E-mail",                       "text", "E-mail"),
    ("www",                 "Strona www",                   "text", "Strona www"),
    ("dyrektor",            "Imię i nazwisko dyrektora",    "text", "Dyrektor"),

    ("publicznosc",         "Publiczność status",           "text", "Publiczność"),
    ("kategoria_uczniow",   "Kategoria uczniów",            "text", "Kategoria uczniów"),
    ("specyfika",           "Specyfika placówki",           "text", "Specyfika"),
    ("liczba_uczniow",      "Liczba uczniów",               "int",  "Uczniów"),
    ("jezyki",              "Języki nauczane",              "text", "Języki"),

    ("organ_typ",           "Typ organu prowadzącego",      "text", "Typ organu"),
    ("organ_nazwa",         "Nazwa organu prowadzącego",    "text", "Organ prowadzący"),
    ("organ_regon",         "REGON organu prowadzącego",    "text", "REGON organu"),

    ("miejsce_w_strukturze", "Miejsce w strukturze",        "text", "Miejsce w strukturze"),
    ("rspo_nadrzedny",      "RSPO podmiotu nadrzędnego",    "text", "RSPO nadrzędnego"),
    ("nazwa_nadrzedna",     "Nazwa podmiotu nadrzędnego",   "text", "Podmiot nadrzędny"),

    ("data_zalozenia",      "Data założenia",               "text", "Data założenia"),
    ("data_likwidacji",     "Data likwidacji",              "text", "Data likwidacji"),
]

KLUCZE_RSPO = [p[0] for p in POLA_RSPO]
NAGLOWKI_RSPO = {p[1]: p[0] for p in POLA_RSPO}
ETYKIETY = {p[0]: p[3] for p in POLA_RSPO}
TYPY_POL = {p[0]: p[2] for p in POLA_RSPO}

# Pola, których zmianę w rejestrze zapisujemy do dziennika `zmiany`. Wszystkie
# poza numerem (klucz) i polami czysto porządkowymi — dziennik ma odpowiadać na
# pytanie „co się zmieniło od zeszłego miesiąca", a nie „co przestawiono w TERYT".
POLA_SLEDZONE = [k for k in KLUCZE_RSPO
                 if k not in ("rspo", "teryt_gmina", "data_zalozenia")]

# ---------------------------------------------------------------------------
# GRUPY TYPÓW — po czym realnie filtruje koordynatorka.
#
# Rejestr ma w samym śląskim 43 różne typy placówek. Lista rozwijana z 43
# pozycjami to nie jest filtr, to spis treści. Dlatego obok pełnej listy typów
# dajemy 6 grup, rozpoznawanych PO SŁOWACH KLUCZOWYCH, a nie po sztywnej liście:
# gdy rejestr doda „Przedszkole integracyjne", wpadnie do przedszkoli samo,
# zamiast wylądować w „innych" i zniknąć koordynatorce z oczu.
#
# Kolejność ma znaczenie — pierwsza pasująca grupa wygrywa („Ogólnokształcąca
# szkoła muzyczna I stopnia" ma trafić do artystycznych, nie do podstawówek).
# ---------------------------------------------------------------------------

GRUPY_TYPOW = [
    ("przedszkola",   "Przedszkola",        ("przedszkol",)),
    ("artystyczne",   "Artystyczne",        ("muzyczn", "plastyczn", "baletow", "tańca",
                                             "artystyczn")),
    ("podstawowki",   "Szkoły podstawowe",  ("szkoła podstawowa",)),
    ("zespoly",       "Zespoły szkół",      ("zespół",)),
    ("ponadpodst",    "Ponadpodstawowe",    ("liceum", "technikum", "branżow", "policealn",
                                             "kształcenia zawodowego", "przysposabiając")),
    # Zajęcia popołudniowe — inny model niż szkoła, ale to nasi odbiorcy.
    # Schroniska i bursy świadomie NIE tutaj: tam się nocuje, nie prowadzi zajęć.
    ("pozaszkolne",   "Pozaszkolne i kultura",
                                            ("młodzieżowy dom kultury", "pałac młodzieży",
                                             "ognisko pracy pozaszkolnej", "pozaszkoln",
                                             "międzyszkolny ośrodek sportowy",
                                             "oświatowo-wychowawcza")),
    ("wsparcie",      "Poradnie i ośrodki", ("poradnia", "ośrodek", "bursa", "biblioteki",
                                             "dom wczasów", "schronisko")),
    ("ustawiczne",    "Kształcenie ustawiczne i dorosłych",
                                            ("kształcenia ustawicznego", "doskonalenia",
                                             "umiejętności")),
]

# Grupy, w których SILESIA 3D realnie prowadzi zajęcia. To domyślny filtr „nasze
# typy" — nie po to, żeby oszczędzać miejsce w bazie (6 tysięcy wierszy to dla
# SQLite nic), tylko żeby koordynatorka nie przewijała liceów w poszukiwaniu
# podstawówki. Zdejmuje się jednym kliknięciem.
NASZE_GRUPY = ["przedszkola", "podstawowki", "zespoly", "pozaszkolne"]


def grupa_typu(typ):
    """Nazwa typu z rejestru → klucz grupy. Nierozpoznane lądują w `inne`."""
    t = (typ or "").lower()
    for klucz, _etykieta, slowa in GRUPY_TYPOW:
        if any(s in t for s in slowa):
            return klucz
    return "inne"


ETYKIETY_GRUP = dict([(k, e) for k, e, _ in GRUPY_TYPOW] + [("inne", "Inne")])


# ---------------------------------------------------------------------------
# Schemat
# ---------------------------------------------------------------------------

def _kolumny_placowek():
    """Definicje kolumn tabeli `placowki` — z pól rejestru plus nasze własne."""
    kol = []
    for klucz, _naglowek, typ, _etykieta in POLA_RSPO:
        if klucz == "rspo":
            kol.append("rspo INTEGER PRIMARY KEY")
        else:
            kol.append("%s %s" % (klucz, "INTEGER" if typ == "int" else "TEXT"))
    kol += [
        # --- nasze, importu nie dotyczą ---
        "objeta INTEGER NOT NULL DEFAULT 0",   # objęta działaniem (ręcznie)
        "notatka TEXT",
        # --- ślad importów ---
        "pierwszy_import TEXT",                # kiedy weszła do bazy
        "ostatni_import TEXT",                 # kiedy ostatnio potwierdził ją plik
        "ostatnia_zmiana TEXT",                # kiedy ostatnio zmieniło się jej pole
        # „Zniknęła z rejestru" — data pierwszego pliku, w którym jej zabrakło.
        # NIE KASUJEMY: placówka mogła się przekształcić albo połączyć, a w aplikacji
        # leadów wisi na niej historia kontaktów. Kasowanie jest nieodwracalne,
        # oznaczenie — nie.
        "nieobecna_od TEXT",
        # --- pod mapę (dziś puste, patrz README) ---
        "lat REAL",
        "lon REAL",
    ]
    return kol


SCHEMAT = """
CREATE TABLE IF NOT EXISTS placowki (%(kolumny)s);

CREATE INDEX IF NOT EXISTS idx_pl_powiat  ON placowki(powiat);
CREATE INDEX IF NOT EXISTS idx_pl_gmina   ON placowki(gmina);
CREATE INDEX IF NOT EXISTS idx_pl_typ     ON placowki(typ);
CREATE INDEX IF NOT EXISTS idx_pl_nazwa   ON placowki(nazwa);

-- Rejon = obszar działania. Placówka nie ma kolumny „rejon", bo rejon wynika
-- z jej powiatu/gminy — inaczej poszerzenie rejonu wymagałoby przepisania
-- tysiąca wierszy zamiast dopisania jednej linijki.
CREATE TABLE IF NOT EXISTS rejony (
  id        INTEGER PRIMARY KEY,
  nazwa     TEXT NOT NULL UNIQUE,
  kolor     TEXT,
  opis      TEXT,
  kolejnosc INTEGER NOT NULL DEFAULT 100
);

-- Jeden obszar (powiat albo gmina) należy do DOKŁADNIE JEDNEGO rejonu —
-- stąd UNIQUE na parze. Bez tego ta sama placówka liczyłaby się w dwóch
-- rejonach naraz i suma po rejonach przestałaby się zgadzać z sumą w bazie,
-- czyli raport przestałby być raportem.
CREATE TABLE IF NOT EXISTS rejon_obszary (
  id       INTEGER PRIMARY KEY,
  rejon_id INTEGER NOT NULL REFERENCES rejony(id) ON DELETE CASCADE,
  rodzaj   TEXT NOT NULL,          -- 'powiat' | 'gmina'
  wartosc  TEXT NOT NULL,
  UNIQUE(rodzaj, wartosc)
);

-- Wyliczona przynależność placówek do rejonów. Tabela pomocnicza, przeliczana
-- po każdym imporcie i po każdej zmianie rejonów (6 tys. wierszy = ułamek
-- sekundy). Trzymamy ją materialnie, żeby lista i liczniki nie robiły przy
-- każdym odświeżeniu ekranu potrójnego JOIN-a z pierwszeństwem gminy nad powiatem.
CREATE TABLE IF NOT EXISTS placowka_rejon (
  rspo     INTEGER PRIMARY KEY,
  rejon_id INTEGER NOT NULL REFERENCES rejony(id) ON DELETE CASCADE,
  przez    TEXT NOT NULL           -- 'gmina:Knurów' / 'powiat:Katowice'
);
CREATE INDEX IF NOT EXISTS idx_pr_rejon ON placowka_rejon(rejon_id);

CREATE TABLE IF NOT EXISTS importy (
  id              INTEGER PRIMARY KEY,
  kiedy           TEXT NOT NULL,
  plik            TEXT,
  rozmiar_mb      REAL,
  zakres          TEXT,            -- 'ŚLĄSKIE' albo 'cała Polska'
  wierszy_w_pliku INTEGER,
  w_zakresie      INTEGER,
  nowych          INTEGER,
  zmienionych     INTEGER,
  bez_zmian       INTEGER,
  zniknelo        INTEGER,
  wrocilo         INTEGER,
  sekundy         REAL,
  uwagi           TEXT
);

-- Dziennik zmian pól. Po co: przy comiesięcznym odświeżeniu jedyne sensowne
-- pytanie brzmi „co się zmieniło od zeszłego razu", a nie „ile jest rekordów".
CREATE TABLE IF NOT EXISTS zmiany (
  id        INTEGER PRIMARY KEY,
  import_id INTEGER NOT NULL REFERENCES importy(id) ON DELETE CASCADE,
  rspo      INTEGER NOT NULL,
  nazwa     TEXT,
  pole      TEXT NOT NULL,
  bylo      TEXT,
  jest      TEXT
);
CREATE INDEX IF NOT EXISTS idx_zm_import ON zmiany(import_id);
"""


def polacz():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def zaloz(conn=None):
    """Tworzy schemat, jeśli go nie ma. Wywoływane przy każdym starcie — tanie."""
    wlasny = conn is None
    conn = conn or polacz()
    try:
        conn.executescript(SCHEMAT % {"kolumny": ",\n  ".join(_kolumny_placowek())})
        _domiar_kolumn(conn)
        conn.commit()
    finally:
        if wlasny:
            conn.close()


def _domiar_kolumn(conn):
    """
    Dokłada kolumny, których brakuje w starszej bazie.

    Po co: rozwijamy narzędzie w trakcie użycia i baza u kogoś na dysku jest
    starsza niż kod. `ALTER TABLE ADD COLUMN` w SQLite jest natychmiastowy
    i bezpieczny — a alternatywą byłoby „skasuj bazę i wgraj plik od nowa",
    czyli utrata flag „objęta działaniem" i notatek.
    """
    ma = {r["name"] for r in conn.execute("PRAGMA table_info(placowki)")}
    for definicja in _kolumny_placowek():
        nazwa = definicja.split()[0]
        if nazwa not in ma:
            conn.execute("ALTER TABLE placowki ADD COLUMN %s" % definicja)


def dzis():
    return dt.date.today().isoformat()


def teraz():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")
