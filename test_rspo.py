# -*- coding: utf-8 -*-
"""
Testy narzędzia RSPO — na małym pliku wzorcowym, na własnej bazie tymczasowej.

CZEGO TE TESTY PILNUJĄ
Jednej obietnicy, na której stoi całe narzędzie: „kolejne wgranie pliku dogrywa
nowe, ale nie robi duplikatów”. Wszystko inne (filtry, rejony, eksport) jest
wygodą — to jest warunek zaufania. Dlatego najwięcej sprawdzeń dotyczy
powtórnego wgrania, zmiany nazwy szkoły i placówki, która zniknęła z rejestru.

Format jak w `leady_app_v5`: zwykły skrypt, bez pytest, uruchamiany jednym
poleceniem, na bazie w katalogu tymczasowym — testy nie mogą dotknąć danych,
na których ktoś pracuje.

Uruchomienie:  python test_rspo.py
"""
import os
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

TMP = tempfile.mkdtemp(prefix="rspo_test_")
os.environ["RSPO_DATA"] = TMP
os.environ["RSPO_DB"] = os.path.join(TMP, "test.db")

import db                       # noqa: E402
import eksport                  # noqa: E402
import magazyn                  # noqa: E402
import plik as plik_mod         # noqa: E402
import rejony                   # noqa: E402
import zapytania                # noqa: E402

WYNIKI = []


def sprawdz(nazwa, warunek, opis=""):
    WYNIKI.append((nazwa, bool(warunek), opis))
    print("  [%s] %s%s" % ("OK  " if warunek else "BLAD", nazwa,
                           (" — " + opis) if opis else ""))
    return bool(warunek)


# ---------------------------------------------------------------------------
# Plik wzorcowy. Kolumn jest 54 w prawdziwym eksporcie, ale importer czyta po
# nagłówkach, więc do testu wystarczy podzbiór — o to właśnie chodzi w teście
# regresji „rejestr przestawił kolumny”.
# ---------------------------------------------------------------------------

NAGLOWKI = ["Numer RSPO", "Nazwa", "Typ", "Województwo", "Powiat", "Gmina",
            "Miejscowość", "Ulica", "Numer budynku", "Kod pocztowy", "Telefon",
            "E-mail", "Imię i nazwisko dyrektora", "Liczba uczniów",
            "Publiczność status", "Data likwidacji", "Miejsce w strukturze",
            "RSPO podmiotu nadrzędnego", "Nazwa podmiotu nadrzędnego"]


def wiersz(rspo, nazwa, typ="Szkoła podstawowa", powiat="Katowice",
           gmina="Katowice", miejscowosc="Katowice", telefon='="032111222"',
           uczniow="120", woj="ŚLĄSKIE", likwidacja="", nadrzedny="", nadnazwa=""):
    return [str(rspo), nazwa, typ, woj, powiat, gmina, miejscowosc, "ul. Testowa",
            '="1"', '="40-001"', telefon, "sekretariat@example.pl", "Jan Kowalski",
            uczniow, "publiczna", likwidacja, "samodzielna", nadrzedny, nadnazwa]


def zapisz_csv(nazwa, wiersze):
    sciezka = os.path.join(TMP, nazwa)
    with open(sciezka, "w", encoding="utf-8-sig", newline="") as f:
        f.write(";".join(NAGLOWKI) + "\n")
        for w in wiersze:
            f.write(";".join(w) + "\n")
    return sciezka


# Baza testowa ma 40 placówek, a nie trzy — inaczej bezpiecznik przy zniknięciach
# (patrz `magazyn.PROG_ZNIKNIEC`) odpalałby się przy każdym normalnym ubytku
# i test sprawdzałby, że mechanizm oznaczania NIE działa. To dokładnie ten rodzaj
# testu, który przechodzi zawsze i nie pilnuje niczego.
SP1 = "SZKOŁA PODSTAWOWA NR 1"
SP1_PO_ZMIANIE = "SZKOŁA PODSTAWOWA NR 1 IM. JANA PAWŁA II"


def baza(nazwa_1001=SP1, telefon_1001='="032111222"', bez=()):
    w = [wiersz(1001, nazwa_1001, telefon=telefon_1001),
         wiersz(1002, "PRZEDSZKOLE NR 5", typ="Przedszkole", uczniow="60"),
         wiersz(1003, "III LICEUM OGÓLNOKSZTAŁCĄCE", typ="Liceum ogólnokształcące")]
    w += [wiersz(1010 + i, "SZKOŁA PODSTAWOWA NR %d" % (i + 2)) for i in range(37)]
    return [x for x in w if int(x[0]) not in bez]


ILE_W_BAZIE = 40


# ---------------------------------------------------------------------------

def main():
    print("Testy narzędzia RSPO (baza tymczasowa: %s)\n" % TMP)
    db.zaloz()
    conn = db.polacz()

    # --- 1. pierwsze wgranie -------------------------------------------------
    print("1. Pierwsze wgranie")
    p1 = zapisz_csv("plik1.csv", baza() + [
        wiersz(1004, "SZKOŁA W GDAŃSKU", woj="POMORSKIE", powiat="Gdańsk", gmina="Gdańsk"),
        wiersz(1005, "SZKOŁA ZLIKWIDOWANA", likwidacja="2024.08.31"),
    ])
    r = magazyn.wgraj(p1, "plik1.csv", conn=conn)
    sprawdz("wchodzą tylko placówki ze śląskiego", r["w_zakresie"] == ILE_W_BAZIE,
            "w zakresie: %d (Gdańsk odpada)" % r["w_zakresie"])
    sprawdz("zlikwidowana pominięta", r["w_zakresie"] == ILE_W_BAZIE)
    sprawdz("wszystkie jako nowe", r["nowych"] == ILE_W_BAZIE)
    sprawdz("telefon bez „pancerza Excela”",
            conn.execute("SELECT telefon FROM placowki WHERE rspo=1001").fetchone()[0]
            == "032111222")
    sprawdz("kod pocztowy z wiodącym zerem zachowany",
            conn.execute("SELECT kod_pocztowy FROM placowki WHERE rspo=1001").fetchone()[0]
            == "40-001")
    sprawdz("liczba uczniów wchodzi jako liczba",
            conn.execute("SELECT liczba_uczniow FROM placowki WHERE rspo=1001").fetchone()[0]
            == 120)

    # --- 2. TO SAMO drugi raz — sedno całego narzędzia ----------------------
    print("\n2. Powtórne wgranie tego samego pliku")
    r = magazyn.wgraj(p1, "plik1.csv", conn=conn)
    ile = conn.execute("SELECT COUNT(*) FROM placowki").fetchone()[0]
    sprawdz("ZERO duplikatów", ile == ILE_W_BAZIE, "w bazie: %d" % ile)
    sprawdz("nic nie uznane za nowe", r["nowych"] == 0)
    sprawdz("nic nie uznane za zmienione", r["zmienionych"] == 0)
    sprawdz("wszystko rozpoznane jako bez zmian", r["bez_zmian"] == ILE_W_BAZIE)

    # --- 3. zmiana nazwy szkoły ---------------------------------------------
    print("\n3. Rejestr zmienia nazwę i telefon")
    p2 = zapisz_csv("plik2.csv", baza(SP1_PO_ZMIANIE, '="032999888"'))
    r = magazyn.wgraj(p2, "plik2.csv", conn=conn)
    w = conn.execute("SELECT nazwa, telefon FROM placowki WHERE rspo=1001").fetchone()
    sprawdz("nazwa zaktualizowana w TYM SAMYM rekordzie",
            w["nazwa"].endswith("JANA PAWŁA II"))
    sprawdz("nie powstał drugi rekord",
            conn.execute("SELECT COUNT(*) FROM placowki").fetchone()[0] == ILE_W_BAZIE)
    sprawdz("telefon zaktualizowany", w["telefon"] == "032999888")
    sprawdz("zmiana trafiła do dziennika",
            any(z["pole"] == "nazwa" for z in magazyn.zmiany_importu(conn, r["import_id"])))

    # --- 4. placówka znika z rejestru ---------------------------------------
    print("\n4. Placówka znika z rejestru")
    p3 = zapisz_csv("plik3.csv", baza(SP1_PO_ZMIANIE, '="032999888"', bez=(1002,)))
    r = magazyn.wgraj(p3, "plik3.csv", conn=conn)
    w = conn.execute("SELECT nieobecna_od FROM placowki WHERE rspo=1002").fetchone()
    sprawdz("oznaczona jako nieobecna", bool(w["nieobecna_od"]))
    sprawdz("NIE skasowana",
            conn.execute("SELECT COUNT(*) FROM placowki").fetchone()[0] == ILE_W_BAZIE)
    sprawdz("policzona w raporcie", r["zniknelo"] == 1)

    print("\n5. Placówka wraca do rejestru")
    r = magazyn.wgraj(p2, "plik2.csv", conn=conn)
    w = conn.execute("SELECT nieobecna_od FROM placowki WHERE rspo=1002").fetchone()
    sprawdz("oznaczenie zdjęte", w["nieobecna_od"] is None)
    sprawdz("powrót policzony", r["wrocilo"] == 1)

    # --- 6. bezpiecznik przy pliku-wycinku ----------------------------------
    print("\n6. Bezpiecznik: ktoś wgrywa plik przefiltrowany w wyszukiwarce")
    p4 = zapisz_csv("wycinek.csv", [wiersz(1001, "SZKOŁA PODSTAWOWA NR 1")])
    r = magazyn.wgraj(p4, "wycinek.csv", conn=conn)
    sprawdz("nic nie oznaczono jako zniknięte", r["zniknelo"] == 0)
    sprawdz("i powiedziano dlaczego",
            any("Wstrzymano" in u for u in r["uwagi"]),
            r["uwagi"][0][:60] if r["uwagi"] else "brak uwagi")

    # --- 7. grupy typów ------------------------------------------------------
    print("\n7. Grupowanie typów")
    sprawdz("„Szkoła podstawowa” → podstawówki",
            db.grupa_typu("Szkoła podstawowa") == "podstawowki")
    sprawdz("„Punkt przedszkolny” → przedszkola",
            db.grupa_typu("Punkt przedszkolny") == "przedszkola")
    sprawdz("nieznany typ z rejestru wpada do przedszkoli po słowie kluczowym",
            db.grupa_typu("Przedszkole integracyjne z oddziałami") == "przedszkola")
    sprawdz("„Ogólnokształcąca szkoła muzyczna I stopnia” → artystyczne, nie podstawówki",
            db.grupa_typu("Ogólnokształcąca szkoła muzyczna I stopnia") == "artystyczne")
    sprawdz("liceum nie jest naszym typem",
            db.grupa_typu("Liceum ogólnokształcące") not in db.NASZE_GRUPY)

    # --- 8. rejony -----------------------------------------------------------
    print("\n8. Rejony i ich poszerzanie")
    rejony.zasiej(conn)
    rejony.przelicz(conn)
    kat = conn.execute("SELECT id FROM rejony WHERE nazwa='Katowice'").fetchone()[0]
    w_kat = conn.execute("SELECT COUNT(*) FROM placowka_rejon WHERE rejon_id=?",
                         (kat,)).fetchone()[0]
    sprawdz("placówki z Katowic wpadły do rejonu Katowice", w_kat == ILE_W_BAZIE,
            "%d" % w_kat)

    _id, kom = rejony.nowy_rejon(conn, "Testowo", "#123456", [("gmina", "Katowice")])
    sprawdz("nowy rejon powstał", _id is not None, kom)
    przez = conn.execute("SELECT przez FROM placowka_rejon WHERE rspo=1001").fetchone()[0]
    sprawdz("GMINA BIJE POWIAT — placówka przeszła do rejonu po gminie",
            przez == "gmina:Katowice", przez)
    rejony.usun_rejon(conn, _id)
    przez = conn.execute("SELECT przez FROM placowka_rejon WHERE rspo=1001").fetchone()[0]
    sprawdz("po usunięciu rejonu wraca przypisanie po powiecie",
            przez == "powiat:Katowice", przez)

    ok, kom = rejony.dodaj_obszar(conn, kat, "powiat", "Bytom")
    sprawdz("poszerzenie rejonu o powiat działa", ok, kom)

    # --- 9. filtry i eksport -------------------------------------------------
    print("\n9. Filtry i eksport")
    _w, razem, _p = zapytania.placowki(conn, {"grupa": "nasze"})
    sprawdz("filtr „nasze typy” odsiewa liceum", razem == ILE_W_BAZIE - 1, "%d" % razem)
    _w, razem, _p = zapytania.placowki(conn, {"q": "PRZEDSZKOLE"})
    sprawdz("szukajka po nazwie", razem == 1, "%d" % razem)
    _w, razem, _p = zapytania.placowki(conn, {"rejon": "brak"})
    sprawdz("filtr „poza rejonami”", razem == 0, "%d" % razem)

    plik_xlsx = os.path.join(TMP, "wykaz.xlsx")
    ile = eksport.zapisz(conn, {"grupa": "nasze"}, plik_xlsx)
    sprawdz("eksport oddaje tyle, ile pokazuje ekran", ile == ILE_W_BAZIE - 1, "%d" % ile)
    try:
        import openpyxl
        ws = openpyxl.load_workbook(plik_xlsx).active
        naglowki = [c.value for c in ws[1]]
        sprawdz("nagłówki wykazu zgodne z importem w aplikacji leadów",
                naglowki == eksport.NAGLOWKI_WYKAZU, str(naglowki))
    except ImportError:
        sprawdz("openpyxl dostępny", False, "brak biblioteki — pominięto")

    # --- 10. rozpoznanie pliku ----------------------------------------------
    print("\n10. Rozpoznawanie pliku")
    obcy = os.path.join(TMP, "obcy.csv")
    with open(obcy, "w", encoding="utf-8") as f:
        f.write("imie;nazwisko\nJan;Kowalski\n")
    ok, brak, _z = plik_mod.sprawdz_naglowki(obcy)
    sprawdz("obcy plik odrzucony przed przetwarzaniem", not ok)
    sprawdz("i wiadomo, czego brakuje", "Numer RSPO" in brak, str(brak))
    ok, _b, _z = plik_mod.sprawdz_naglowki(p1)
    sprawdz("prawdziwy eksport rozpoznany", ok)

    conn.close()
    ile_ok = sum(1 for _, w, _ in WYNIKI if w)
    print("\n== %d/%d sprawdzeń OK ==" % (ile_ok, len(WYNIKI)))
    return 0 if ile_ok == len(WYNIKI) else 1


if __name__ == "__main__":
    sys.exit(main())
