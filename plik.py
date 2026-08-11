# -*- coding: utf-8 -*-
"""
Czytanie pliku pobranego z rspo.gov.pl.

SKĄD SIĘ BIERZE PLIK
rspo.gov.pl → wyszukiwarka → „Pobierz wyniki" → CSV (średnik jako separator,
BOM na początku, 54 kolumny, cała Polska to ~42 MB i 56 tysięcy wierszy).
Obsługujemy też .xlsx, bo ktoś po drodze potrafi otworzyć plik w Excelu
i zapisać „żeby ładniej wyglądał" — a wtedy CSV przestaje być CSV-em.

DWIE PUŁAPKI TEGO PLIKU, obie już nas kosztowały czas:

1. „Pancerz Excela". Rejestr zapisuje część pól jako ="0123", żeby arkusz nie
   zjadł wiodącego zera z numeru telefonu albo kodu pocztowego. Bez zdjęcia
   tego pancerza telefon trafiłby do bazy jako `="604616936"` i nie dałoby się
   go kliknąć ani skopiować.

2. Kodowanie. Bywa utf-8 z BOM-em, bywa cp1250. Zgadujemy po kolei, zamiast
   zakładać jedno i wysypywać się na drugim.

CZEGO W TYM PLIKU NIE MA: WSPÓŁRZĘDNYCH.
Sprawdzone kolumna po kolumnie — 54 kolumny i ani jednej z szerokością/długością
geograficzną. Jest za to `Kod terytorialny gmina` (TERYT), na którym da się
oprzeć mapę rejonów. Szczegóły w README, sekcja „Mapa".
"""
import collections
import csv
import os
import re

import db

csv.field_size_limit(10_000_000)

_PANCERZ = re.compile(r'^="(.*)"$', re.S)


def czysc(v):
    """Zdejmuje `="…"` i przycina białe znaki. Patrz pułapka 1 w nagłówku."""
    s = ("" if v is None else str(v)).strip()
    m = _PANCERZ.match(s)
    if m:
        s = m.group(1)
    return s.strip()


def _otworz_csv(sciezka):
    """CSV z RSPO bywa z BOM-em, bywa w cp1250 — próbujemy po kolei."""
    for kod in ("utf-8-sig", "utf-8", "cp1250"):
        try:
            f = open(sciezka, encoding=kod, newline="")
            f.readline()
            f.seek(0)
            return f, kod
        except UnicodeDecodeError:
            continue
    raise ValueError("Nie umiem odczytać pliku — nieznane kodowanie")


def _wiersze_csv(sciezka):
    f, kod = _otworz_csv(sciezka)
    with f:
        # Separator: rejestr daje średnik, ale gdyby kiedyś dał przecinek,
        # lepiej to wykryć niż wczytać cały plik jako jedną kolumnę.
        probka = f.readline()
        f.seek(0)
        sep = ";" if probka.count(";") >= probka.count(",") else ","
        for w in csv.DictReader(f, delimiter=sep):
            yield w
    return


def _wiersze_xlsx(sciezka):
    import openpyxl
    wb = openpyxl.load_workbook(sciezka, read_only=True, data_only=True)
    ws = wb.active
    naglowki = None
    for wiersz in ws.iter_rows(values_only=True):
        if naglowki is None:
            naglowki = [czysc(c) for c in wiersz]
            continue
        yield dict(zip(naglowki, wiersz))
    wb.close()


def sprawdz_naglowki(sciezka):
    """
    Zwraca (ok, brakujace, znalezione) — czy plik w ogóle wygląda na eksport z RSPO.

    Po co osobno: komunikat „nie znalazłem kolumny »Numer RSPO«" jest dla
    koordynatorki użyteczny, a `KeyError` w połowie importu 56 tysięcy wierszy
    nie jest. Sprawdzamy sam nagłówek, zanim ruszy przetwarzanie.
    """
    zrodlo = _wiersze_xlsx if sciezka.lower().endswith((".xlsx", ".xlsm")) else _wiersze_csv
    try:
        pierwszy = next(iter(zrodlo(sciezka)))
    except StopIteration:
        return False, ["plik jest pusty"], []
    znalezione = [czysc(k) for k in pierwszy.keys() if k]
    wymagane = ["Numer RSPO", "Nazwa", "Typ", "Województwo", "Powiat", "Gmina"]
    brak = [k for k in wymagane if k not in znalezione]
    return (not brak), brak, znalezione


def czytaj(sciezka, wojewodztwo=db.WOJEWODZTWO_DOMYSLNE, pomijaj_zlikwidowane=True):
    """
    Czyta plik i zwraca (lista_wierszy_do_bazy, statystyki).

    `wojewodztwo=None` → cała Polska. Domyślnie ŚLĄSKIE, bo firma działa na
    Śląsku, a 56 tysięcy wierszy z całego kraju to 50 tysięcy pozycji, po których
    nikt nigdy nie zadzwoni.

    Placówki zlikwidowane pomijamy — mają datę likwidacji i nie ma do kogo w nich
    dzwonić. UWAGA: w eksporcie z wyszukiwarki ta kolumna jest pusta w całym
    pliku (wyszukiwarka oddaje wyłącznie czynne placówki), więc ten filtr jest
    zabezpieczeniem na wypadek innego eksportu, a nie realnym sitem. Wykrycie
    „placówka zniknęła z rejestru" robimy przez porównanie z poprzednim stanem
    bazy — patrz `magazyn.wgraj`.
    """
    zrodlo = _wiersze_xlsx if sciezka.lower().endswith((".xlsx", ".xlsm")) else _wiersze_csv
    woj = (wojewodztwo or "").strip().upper()

    stat = collections.Counter()
    wg_typu = collections.Counter()
    wg_powiatu = collections.Counter()
    out = []
    widziane = set()

    for w in zrodlo(sciezka):
        stat["wierszy"] += 1
        if woj and czysc(w.get("Województwo")).upper() != woj:
            continue
        if pomijaj_zlikwidowane and czysc(w.get("Data likwidacji")):
            stat["zlikwidowane"] += 1
            continue

        rekord = {}
        for klucz, naglowek, typ, _et in db.POLA_RSPO:
            wartosc = czysc(w.get(naglowek))
            if typ == "int":
                # „0" w liczbie uczniów u placówki bez uczniów jest prawdziwym
                # zerem, ale pusty string to brak danych — a to dwie różne rzeczy
                # przy sortowaniu „od największej szkoły".
                rekord[klucz] = int(wartosc) if wartosc.isdigit() else None
            else:
                rekord[klucz] = wartosc or None

        if not rekord["rspo"]:
            stat["bez_numeru"] += 1
            continue
        # Ten sam numer dwa razy w jednym pliku zdarzył się już przy plikach
        # klienta. Bierzemy pierwsze wystąpienie i liczymy resztę — inaczej
        # licznik „nowych" pokazałby liczbę wierszy, a nie liczbę placówek.
        if rekord["rspo"] in widziane:
            stat["powtorki_w_pliku"] += 1
            continue
        widziane.add(rekord["rspo"])

        out.append(rekord)
        stat["w_zakresie"] += 1
        wg_typu[rekord["typ"] or "—"] += 1
        wg_powiatu[rekord["powiat"] or "—"] += 1

    stat["wg_typu"] = wg_typu
    stat["wg_powiatu"] = wg_powiatu
    return out, stat


def adres(rekord):
    """„ul. Orla 6/8" — z trzech kolumn rejestru, bo aplikacja leadów chce jedną."""
    czesci = [rekord.get("ulica") or "", rekord.get("nr_budynku") or ""]
    a = " ".join(c for c in czesci if c).strip()
    if rekord.get("nr_lokalu"):
        a = (a + "/" + rekord["nr_lokalu"]).strip("/")
    return a


def rozmiar_mb(sciezka):
    try:
        return round(os.path.getsize(sciezka) / (1024 * 1024), 1)
    except OSError:
        return None
